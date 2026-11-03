"""Recover source facts from a bounded Notion-style Markdown/CSV export.

No archive member is extracted to disk, and no remote URL is fetched.
"""

import base64
import csv
import hashlib
import io
import posixpath
import re
import stat
import zipfile
from datetime import datetime, timezone
from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit

MAX_ARCHIVE = 20 * 1024 * 1024
MAX_EXPANDED = 16 * 1024 * 1024
MAX_ENTRY = 2 * 1024 * 1024
MAX_ASSETS = 3 * 1024 * 1024
MAX_FILES = 1000
UUID = re.compile(r"([a-fA-F0-9]{32}|[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12})$")
LINK = re.compile(r"!?\[([^\]]*)\]\(([^\n)]+)\)")
CHECK = re.compile(r"^\s*[-*]\s+\[([ xX])\]\s+(.+)$", re.MULTILINE)
ASSET_TYPES = {'.txt': 'text/plain', '.pdf': 'application/pdf', '.png': 'image/png',
               '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp',
               '.gif': 'image/gif'}


class ImportFailure(ValueError):
    """An archive cannot safely be recovered."""


def recover_archive(data: bytes, filename: str = "workspace.zip") -> dict:
    if len(data) > MAX_ARCHIVE:
        raise ImportFailure("The ZIP exceeds the 20 MB import limit.")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as bundle:
            files = _read_members(bundle)
    except (zipfile.BadZipFile, RuntimeError, OSError, NotImplementedError) as exc:
        raise ImportFailure("This is not a supported, unencrypted ZIP archive.") from exc
    warnings = []
    pages, databases, assets = [], [], {}
    paths, identifiers = {}, {}
    asset_bytes = 0
    for path, raw in sorted(files.items()):
        suffix = PurePosixPath(path).suffix.lower()
        if suffix == '.md':
            text = _text(raw, path)
            key = _identifier(path)
            if key in identifiers:
                raise ImportFailure("Two pages share the same source identifier; resolve this before import.")
            identifiers[key] = path
            title = next((x[2:].strip() for x in text.splitlines() if x.startswith('# ')), _title(path))
            page = _page(key, title, text, path)
            pages.append(page)
            paths[path] = key
        elif suffix == '.csv':
            databases.append({'id': _identifier(path), 'title': _title(path), 'source': path,
                              'fields': [], 'rows': [], '_raw': _text(raw, path)})
        elif suffix in ASSET_TYPES:
            asset_bytes += len(raw)
            if asset_bytes > MAX_ASSETS:
                raise ImportFailure("Attachments exceed the 3 MB portable-app limit. Export a smaller workspace.")
            key = hashlib.sha256(path.encode()).hexdigest()[:20]
            assets[key] = {'id': key, 'name': PurePosixPath(path).name, 'source': path,
                           'size': len(raw), 'mime': ASSET_TYPES[suffix],
                           'data': base64.b64encode(raw).decode('ascii')}
            paths[path] = 'asset:' + key
        else:
            warnings.append(f"Unsupported file kept out of the application: {path}")
    if not pages and not databases:
        raise ImportFailure("No Markdown pages or CSV databases found. Choose a Notion Markdown & CSV export.")

    for database in databases:
        _merge_rows(database, pages, warnings)
    by_id = {x['id']: x for x in pages}
    by_title = {}
    for page in pages:
        by_title.setdefault(page['title'].casefold(), []).append(page)

    for page in pages:
        for match in LINK.finditer(page['body']):
            label, href = match.groups()
            href = href.strip().strip('<>')
            parsed = urlsplit(href)
            if parsed.scheme or parsed.netloc:
                if parsed.scheme in ('http', 'https'):
                    page['links'].append({'label': label, 'href': href, 'target': None, 'external': True})
                else:
                    warnings.append(f"Blocked non-web link in {page['source']}")
                continue
            path = posixpath.normpath(posixpath.join(posixpath.dirname(page['source']), unquote(parsed.path)))
            target = paths.get(path)
            if not target:
                key = _source_uuid(unquote(parsed.path))
                target = key if key in by_id else None
            if target and target.startswith('asset:'):
                page['attachments'].append(target[6:])
            elif target:
                page['links'].append({'label': label, 'href': href, 'target': target, 'external': False})
            elif href.startswith('#'):
                continue
            else:
                warnings.append(f"Unresolved local link in {page['source']}: {label or href}")
        for field, value in page['properties'].items():
            if field.casefold() in ('name', 'title', 'status', 'stage', 'due', 'due date', 'priority'):
                continue
            candidates = by_title.get(value.casefold(), [])
            if len(candidates) == 1 and candidates[0]['id'] != page['id']:
                page['relations'].append({'field': field, 'target': candidates[0]['id'],
                                          'basis': 'unique-title-candidate', 'confirmed': False})
            elif len(candidates) > 1:
                warnings.append(f"Ambiguous relation in {page['title']}: {field} = {value}; left unresolved.")

    fields = list(dict.fromkeys(f for d in databases for f in d['fields']))
    status_field = next((f for f in fields if f.casefold() in ('status', 'stage')), '')
    states = list(dict.fromkeys(by_id[key]['properties'].get(status_field, '')
                               for database in databases for key in database['rows']))
    states = [x for x in states if x]
    warnings.append("Views, formulas, permissions and automations are not established by this export. Review workflow rules explicitly.")
    return {
        'schema_version': 1,
        'id': hashlib.sha256(data).hexdigest()[:20],
        'name': PurePosixPath(filename.replace('\\', '/')).stem or 'Recovered workspace',
        'pages': pages, 'databases': databases, 'assets': assets,
        'warnings': list(dict.fromkeys(warnings)),
        'workflow': {'field': status_field, 'states': states, 'delivery_state': '',
                     'require_checklist': True, 'followup': '', 'confirmed': False,
                     'basis': 'Not recovered: requires an explicit user declaration'},
        'tasks': [], 'activity': [],
        'provenance': {'mode': 'local-parser', 'source': filename, 'sample': False,
                       'imported_at': datetime.now(timezone.utc).isoformat(),
                       'cloud_calls': [], 'source_files': len(files),
                       'parser_workflow': {'field':status_field,'states':list(states),'delivery_state':''}},
    }


def _read_members(bundle):
    infos = bundle.infolist()
    if len(infos) > MAX_FILES:
        raise ImportFailure("The archive contains more than 1,000 members.")
    total = 0
    files = {}
    for info in infos:
        path = info.filename.replace('\\', '/')
        decoded = unquote(path)
        if decoded.startswith('/') or ':' in decoded or '..' in PurePosixPath(decoded).parts:
            raise ImportFailure("The archive contains an unsafe member path.")
        if stat.S_ISLNK(info.external_attr >> 16):
            raise ImportFailure("Symbolic links are not supported in exports.")
        if info.is_dir() or path.startswith('__MACOSX/'):
            continue
        if info.flag_bits & 1:
            raise ImportFailure("Encrypted ZIP entries are not supported.")
        total += info.file_size
        if total > MAX_EXPANDED or info.file_size > MAX_ENTRY:
            raise ImportFailure("Expanded archive limits exceeded (16 MB total, 2 MB per file).")
        if info.file_size > 100_000 and info.file_size / max(1, info.compress_size) > 1000:
            raise ImportFailure("Suspicious archive compression ratio.")
        normalized = posixpath.normpath(path)
        if normalized in files:
            raise ImportFailure("Duplicate archive paths are not supported.")
        files[normalized] = bundle.read(info)
    return files


def _text(raw, path):
    try:
        return raw.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise ImportFailure(f"A page or database is not UTF-8 text: {path}") from exc


def _source_uuid(path):
    match = UUID.search(PurePosixPath(path).stem)
    return match.group(1).replace('-', '').lower() if match else None


def _identifier(path):
    return _source_uuid(path) or hashlib.sha256(path.encode()).hexdigest()[:32]


def _title(path):
    return UUID.sub('', PurePosixPath(path).stem).strip() or 'Untitled'


def _page(key, title, body, source):
    return {'id': key, 'title': title, 'body': body, 'source': source, 'database': None,
            'properties': {}, 'links': [], 'relations': [], 'attachments': [],
            'checklist': [{'id': f'{key}-check-{i}', 'text': m.group(2), 'done': m.group(1).lower() == 'x'}
                          for i, m in enumerate(CHECK.finditer(body))]}


def _merge_rows(database, pages, warnings):
    try:
        reader = csv.DictReader(io.StringIO(database.pop('_raw')))
        fields = reader.fieldnames or []
        if not fields or len(fields) > 60 or len(set(fields)) != len(fields):
            raise ImportFailure("A database has missing, duplicate or excessive field names.")
        database['fields'] = fields
        title_field = next((x for x in fields if x.casefold() in ('name', 'title')), fields[0])
        for number, row in enumerate(reader):
            if number >= 500 or None in row:
                raise ImportFailure("A database exceeds 500 rows or contains malformed columns.")
            values = {k: (v or '') for k, v in row.items()}
            title = values[title_field].strip() or f'Untitled {number + 1}'
            candidates = [p for p in pages if p['title'].casefold() == title.casefold() and not p['database']]
            folder = str(PurePosixPath(database['source']).with_suffix(''))
            scoped = [p for p in candidates if p['source'].startswith(folder + '/')]
            candidates = scoped or candidates
            if len(candidates) == 1:
                page = candidates[0]
            else:
                if len(pages) >= 1000:
                    raise ImportFailure("The workspace exceeds the 1,000-page recovery limit.")
                key = hashlib.sha256(f"{database['source']}:{number}".encode()).hexdigest()[:32]
                page = _page(key, title, '', database['source'] + f'#row-{number + 1}')
                pages.append(page)
                if len(candidates) > 1:
                    warnings.append(f"Ambiguous page match for database row {title}; kept separate.")
            page['database'] = database['id']
            page['properties'].update(values)
            database['rows'].append(page['id'])
    except csv.Error as exc:
        raise ImportFailure("A database contains invalid CSV.") from exc
