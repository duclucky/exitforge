"""Compile a validated workspace into a network-independent HTML application."""

import html
import json
import base64
import binascii
import math
import re
from datetime import datetime
from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / 'static'


def validate_workspace(project):
    if not isinstance(project, dict) or project.get('schema_version') != 1:
        raise ValueError('Unsupported workspace format.')
    if not isinstance(project.get('id'), str) or not isinstance(project.get('name'), str):
        raise ValueError('Workspace identity is missing.')
    pages = project.get('pages')
    if not isinstance(pages, list) or not pages or len(pages) > 1000:
        raise ValueError('A workspace needs between 1 and 1,000 pages.')
    ids = set()
    for page in pages:
        if not isinstance(page, dict) or any(not isinstance(page.get(k), str) for k in ('id', 'title', 'body', 'source')):
            raise ValueError('Invalid page data.')
        if page['id'] in ids:
            raise ValueError('Duplicate page identifiers.')
        ids.add(page['id'])
        if 'local_record' in page:
            origin=page['local_record']
            try:
                stamp=origin['created_at']
                valid_stamp=isinstance(stamp,str) and stamp.endswith('Z') and datetime.fromisoformat(stamp).isoformat(timespec='milliseconds').replace('+00:00','Z')==stamp
            except (KeyError,TypeError,ValueError):valid_stamp=False
            if (not isinstance(origin,dict) or set(origin)!={'created_at'} or not valid_stamp
                or not re.fullmatch(r'local-[A-Za-z0-9_-]{1,80}',page['id']) or page['source']!='ExitForge-created/'+page['id']+'.md'):
                raise ValueError('Invalid local record origin.')
        if not isinstance(page.get('properties'), dict) or any(not isinstance(v, str) for v in page['properties'].values()):
            raise ValueError('Properties must contain text values.')
        for key in ('links', 'relations', 'attachments', 'checklist'):
            if not isinstance(page.get(key), list):
                raise ValueError('Invalid page collections.')
        if any(not isinstance(c, dict) or not isinstance(c.get('text'), str) or not isinstance(c.get('done'), bool) for c in page['checklist']):
            raise ValueError('Invalid checklist.')
        if any(not isinstance(link,dict) or not isinstance(link.get('href'),str) or not isinstance(link.get('label'),str)
               or not isinstance(link.get('external'),bool) or (link.get('target') is not None and not isinstance(link['target'],str)) for link in page['links']):
            raise ValueError('Invalid page links.')
        if any(not isinstance(link,dict) or not isinstance(link.get('field'),str) or not isinstance(link.get('target'),str)
               or not isinstance(link.get('confirmed'),bool) for link in page['relations']):
            raise ValueError('Invalid page relations.')
        if any(not isinstance(key,str) for key in page['attachments']):
            raise ValueError('Invalid attachment references.')
    if not isinstance(project.get('assets'), dict) or not isinstance(project.get('databases'), list):
        raise ValueError('Invalid assets or databases.')
    allowed = {'text/plain', 'application/pdf', 'image/png', 'image/jpeg', 'image/webp', 'image/gif'}
    asset_size=0
    extensions={'.txt','.pdf','.png','.jpg','.jpeg','.webp','.gif'}
    for key, asset in project['assets'].items():
        if not isinstance(asset, dict) or asset.get('mime') not in allowed or any(not isinstance(asset.get(k), str) for k in ('name', 'data')):
            raise ValueError('Unsupported attachment format.')
        if Path(asset['name']).name!=asset['name'] or Path(asset['name']).suffix.lower() not in extensions:
            raise ValueError('Unsupported attachment filename.')
        try:asset_size+=len(base64.b64decode(asset['data'],validate=True))
        except (ValueError,binascii.Error):raise ValueError('Invalid attachment data.') from None
    if asset_size>3*1024*1024:
        raise ValueError('Attachments exceed the 3 MB portable-app limit.')
    for page in pages:
        if any(link['target'] is not None and link['target'] not in ids for link in page['links']):
            raise ValueError('A page link targets a missing page.')
        if any(link['target'] not in ids for link in page['relations']):
            raise ValueError('A relation targets a missing page.')
        if any(key not in project['assets'] for key in page['attachments']):
            raise ValueError('An attachment is missing.')
    database_ids = set()
    for database in project['databases']:
        if (not isinstance(database,dict) or not isinstance(database.get('id'),str)
            or not isinstance(database.get('fields'),list) or not isinstance(database.get('rows'),list)
            or database['id'] in database_ids
            or any(not isinstance(x,str) for x in database['fields']) or any(x not in ids for x in database['rows'])):
            raise ValueError('Invalid database references.')
        database_ids.add(database['id'])
    rule = project.get('workflow')
    if not isinstance(rule, dict) or not isinstance(rule.get('field'), str) or not isinstance(rule.get('states'), list):
        raise ValueError('Invalid workflow specification.')
    if any(not isinstance(x, str) for x in rule['states']) or not isinstance(rule.get('confirmed'), bool):
        raise ValueError('Invalid workflow states.')
    if len(rule['states'])>8 or len(set(rule['states']))!=len(rule['states']) or any(len(x)>100 for x in rule['states']):
        raise ValueError('Use at most eight bounded workflow stages.')
    if any(not isinstance(rule.get(k), str) for k in ('delivery_state', 'followup')) or not isinstance(rule.get('require_checklist'), bool):
        raise ValueError('Invalid workflow action.')
    if not isinstance(project.get('tasks'), list) or not isinstance(project.get('activity'), list) or not isinstance(project.get('warnings'), list):
        raise ValueError('Invalid workspace history.')
    if not isinstance(project.get('provenance'), dict):
        raise ValueError('Invalid provenance.')
    if any(not isinstance(task,dict) or any(not isinstance(task.get(k),str) for k in ('id','page','text'))
           or not isinstance(task.get('done'),bool) or task['page'] not in ids for task in project['tasks']):
        raise ValueError('Invalid follow-up tasks.')
    if len({task['id'] for task in project['tasks']}) != len(project['tasks']):
        raise ValueError('Duplicate follow-up task identifiers.')
    if any(not isinstance(event,dict) or not isinstance(event.get('text'),str) or not isinstance(event.get('at'),str) for event in project['activity']):
        raise ValueError('Invalid activity history.')
    if any(not isinstance(w,str) for w in project['warnings']):
        raise ValueError('Invalid recovery warnings.')
    if 'cloud_calls' in project['provenance'] and not isinstance(project['provenance']['cloud_calls'], list):
        raise ValueError('Invalid cloud call history.')
    if 'presentation' in project:
        view = project['presentation']
        if (not isinstance(view, dict) or view.get('primary_view') not in ('board','docs')
                or view.get('database_id', '') not in database_ids | {''}):
            raise ValueError('Invalid view configuration.')
    if 'ai_review' in project:
        review = project['ai_review']
        spec = review.get('specification') if isinstance(review, dict) else None
        if (not isinstance(spec, dict) or not isinstance(spec.get('rationale'), str)
                or not isinstance(spec.get('unknowns'), list)
                or any(not isinstance(item, str) for item in spec['unknowns'])
                or not isinstance(review.get('calls'), list)):
            raise ValueError('Invalid AI review.')
        for call in review['calls']:
            if (not isinstance(call, dict) or not isinstance(call.get('provider'), str)
                    or type(call.get('elapsed_ms')) not in (int, float) or not math.isfinite(call['elapsed_ms'])):
                raise ValueError('Invalid AI call history.')
    if len(json.dumps(project)) > 12 * 1024 * 1024:
        raise ValueError('Workspace exceeds the 12 MB packaging limit.')
    if 'process' in project:
        from .processes import validate_process
        validate_process(project,project['process'])
    if 'process_review' in project:
        review=project['process_review']
        if (not isinstance(review,dict) or 'process' not in project or not isinstance(review.get('proposal'),dict)
            or not isinstance(review.get('calls'),list) or not isinstance(review.get('observations'),list)):
            raise ValueError('Invalid process review history.')
        for call in review['calls']:
            if not isinstance(call,dict) or not isinstance(call.get('provider'),str) or type(call.get('elapsed_ms')) not in (int,float) or not math.isfinite(call['elapsed_ms']):
                raise ValueError('Invalid process call history.')
        if len(review['observations'])>6 or any(not isinstance(item,dict) or not isinstance(item.get('id'),str) or not isinstance(item.get('sha256'),str) or len(item['sha256'])!=64 for item in review['observations']):
            raise ValueError('Invalid process observation history.')
    return project


def json_for_script(value):
    return json.dumps(value, ensure_ascii=True).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')


def compile_application(project):
    validate_workspace(project)
    css = (STATIC / 'style.css').read_text(encoding='utf-8')
    runtime = (STATIC / 'runtime.js').read_text(encoding='utf-8')
    workspace = (STATIC / 'workspace.js').read_text(encoding='utf-8')
    process = (STATIC / 'process.js').read_text(encoding='utf-8')
    process_ui = (STATIC / 'process-ui.js').read_text(encoding='utf-8')
    records = (STATIC / 'process-records.js').read_text(encoding='utf-8')
    record_form = (STATIC / 'process-record-form.js').read_text(encoding='utf-8')
    handoff = (STATIC / 'handoff.js').read_text(encoding='utf-8')
    handoff_view = (STATIC / 'handoff-view.js').read_text(encoding='utf-8')
    title = html.escape(project['name'])
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; connect-src 'none'; base-uri 'none'; form-action 'none'">
<title>{title} — Independent workspace</title><style>{css}</style></head>
<body class="portable"><a class="skip-link" href="#workspace-main">Skip to workspace</a><main id="workspace-main"></main>
<script id="workspace-data" type="application/json">{json_for_script(project)}</script>
<script>{process}</script><script>{workspace}</script><script>{records}</script><script>{runtime}</script><script>{record_form}</script><script>{handoff}</script><script>{handoff_view}</script><script>{process_ui}</script><script>ExitForge.mount(document.getElementById('workspace-main'),JSON.parse(document.getElementById('workspace-data').textContent),{{portable:true}});</script>
</body></html>'''
