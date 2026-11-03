"""Bounded hosted inference: private credentials and a durable admission ledger."""
import base64
from contextlib import contextmanager
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import socket
import sqlite3
import struct
import time

from . import providers

RESERVATION = 150_000  # USD millionths; retained even on failed/unknown usage.
LIFETIME_LIMIT = 600_000
DAY = 86400
COOKIE = '__Host-exitforge-ai'


class AdmissionError(providers.ProviderFailure):
    def __init__(self, message, code=429):
        super().__init__(message)
        self.code = code


class Ledger:
    def __init__(self, path, clock=time.time):
        self.path = str(path)
        self.clock = clock
        try:
            self.allowance = int(os.getenv('EXITFORGE_AI_ALLOWANCE_MICROUSD', str(LIFETIME_LIMIT)))
        except ValueError:
            raise AdmissionError('Invalid owner AI allowance configuration. No model call was made.', 503) from None
        if self.allowance not in (LIFETIME_LIMIT, 750_000):
            raise AdmissionError('Owner AI allowance exceeds the approved bounded configuration.', 503)
        with self.transaction() as db:
            db.executescript('''
              CREATE TABLE IF NOT EXISTS settings (name TEXT PRIMARY KEY, value TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, client TEXT NOT NULL, created REAL NOT NULL);
              CREATE TABLE IF NOT EXISTS calls (id TEXT PRIMARY KEY, session TEXT NOT NULL,
                client TEXT NOT NULL, created REAL NOT NULL, state TEXT NOT NULL, usage TEXT NOT NULL DEFAULT '{}');
            ''')
            db.execute('INSERT OR IGNORE INTO settings VALUES (?,?)', ('identity_key', secrets.token_hex(32)))

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=3, isolation_level=None)
        try:
            db.execute('PRAGMA busy_timeout=3000')
            db.execute('BEGIN IMMEDIATE')
            yield db
            if db.in_transaction:
                db.commit()
        except Exception:
            if db.in_transaction:
                db.rollback()
            raise
        finally:
            db.close()

    def client(self, address):
        with self.transaction() as db:
            seed = db.execute('SELECT value FROM settings WHERE name=?', ('identity_key',)).fetchone()[0]
        return hmac.new(seed.encode(), address.encode(), hashlib.sha256).hexdigest()

    def session(self, token, client):
        now = self.clock()
        with self.transaction() as db:
            db.execute('DELETE FROM sessions WHERE created < ?', (now-DAY,))
            identity = hashlib.sha256(token.encode()).hexdigest() if token else ''
            valid = db.execute('SELECT 1 FROM sessions WHERE id=? AND client=?', (identity, client)).fetchone()
            if not valid:
                if db.execute('SELECT COUNT(*) FROM sessions WHERE client=?', (client,)).fetchone()[0] >= 8:
                    raise AdmissionError('Too many trial sessions from this network. Try again tomorrow.')
                if db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0] >= 4096:
                    raise AdmissionError('Trial sessions are temporarily full. Continue manual review.')
                token = secrets.token_urlsafe(32)
                identity = hashlib.sha256(token.encode()).hexdigest()
                db.execute('INSERT INTO sessions VALUES (?,?,?)', (identity, client, now))
            remaining = self._remaining(db, identity, client, now)
        return token, {'available': remaining > 0, 'remaining': remaining,
                       'session_limit': 2, 'network_daily_limit': 3,
                       'notice': 'Shared limited trial. One model call per operation; failed attempts use allowance too. No automatic retries. Manual review and exports stay available.'}

    def _remaining(self, db, session, client, now):
        total = db.execute('SELECT COUNT(*) FROM calls').fetchone()[0]
        own = db.execute('SELECT COUNT(*) FROM calls WHERE session=? AND created>?', (session, now-DAY)).fetchone()[0]
        network = db.execute('SELECT COUNT(*) FROM calls WHERE client=? AND created>?', (client, now-DAY)).fetchone()[0]
        return max(0, min((self.allowance-total*RESERVATION)//RESERVATION, 2-own, 3-network))

    def remaining_global(self):
        with self.transaction() as db:
            count = db.execute('SELECT COUNT(*) FROM calls').fetchone()[0]
        return max(0, (self.allowance-count*RESERVATION)//RESERVATION)

    def reserve(self, token, client, request_id):
        if not re.fullmatch(r'[A-Za-z0-9_-]{16,80}', request_id):
            raise AdmissionError('A valid operation ID is required. Reload and try again.', 400)
        identity = hashlib.sha256(token.encode()).hexdigest()
        call = hashlib.sha256((identity+':'+request_id).encode()).hexdigest()
        now = self.clock()
        with self.transaction() as db:
            if not db.execute('SELECT 1 FROM sessions WHERE id=? AND client=? AND created>?', (identity, client, now-DAY)).fetchone():
                raise AdmissionError('Start a new trial session before requesting AI.', 403)
            if db.execute('SELECT 1 FROM calls WHERE id=?', (call,)).fetchone():
                raise AdmissionError('This operation was already attempted. No duplicate call was made; keep any result already received.', 409)
            if self._remaining(db, identity, client, now) <= 0:
                raise AdmissionError('This session, network or shared trial has reached its AI allowance. Continue manual review or download your work.')
            last = db.execute('SELECT MAX(created) FROM calls WHERE client=?', (client,)).fetchone()[0]
            if last is not None and now-last < 20:
                raise AdmissionError('Please wait 20 seconds between AI operations.')
            if db.execute("SELECT 1 FROM calls WHERE state='pending' AND created>?", (now-180,)).fetchone():
                raise AdmissionError('Another AI operation is running. Try later; no allowance was used for this request.')
            db.execute('INSERT INTO calls (id,session,client,created,state) VALUES (?,?,?,?,?)', (call, identity, client, now, 'pending'))
        return call

    def finish(self, call, succeeded, usage=None):
        safe = {k: v for k, v in (usage or {}).items() if k in ('prompt_tokens', 'completion_tokens', 'total_tokens') and type(v) is int and v >= 0}
        with self.transaction() as db:
            db.execute('UPDATE calls SET state=?,usage=? WHERE id=?', ('completed' if succeeded else 'failed', json.dumps(safe), call))


def configured():
    return (os.getenv('EXITFORGE_PUBLIC_AI') == '1' and os.getenv('EXITFORGE_ALLOW_CLOUD') == '1'
            and bool(os.getenv('EXITFORGE_AI_LEDGER')) and bool(providers.baseten_key()))


def ledger():
    if not configured():
        raise AdmissionError('Hosted AI is not available. Continue manual review.', 503)
    try:
        return Ledger(os.environ['EXITFORGE_AI_LEDGER'])
    except (sqlite3.Error, OSError):
        raise AdmissionError('AI allowance storage is unavailable. No model call was made. Continue manual review.', 503) from None


def client_address(scope, headers):
    peer = scope.get('client', ('unknown', 0))[0]
    # Only the dedicated tunnel peer may supply Cloudflare's overwritten client header.
    if os.getenv('EXITFORGE_TRUST_TUNNEL') == '1':
        try:
            trusted = {x[4][0] for x in socket.getaddrinfo('exitforge-tunnel', None)}
            value = headers.get('CF-Connecting-IP', '')
            if peer in trusted:
                return str(ipaddress.ip_address(value))
        except (OSError, ValueError):
            pass
    return peer


def image_size(raw):
    if raw.startswith(b'\x89PNG\r\n\x1a\n') and len(raw) >= 24:
        return struct.unpack('>II', raw[16:24])
    if raw.startswith(b'\xff\xd8'):
        position = 2
        while position+4 <= len(raw):
            if raw[position] != 255:
                break
            marker = raw[position+1]
            position += 2
            if marker in (0xD8, 0xD9):
                continue
            size = int.from_bytes(raw[position:position+2], 'big')
            if size < 2:
                break
            if marker in (0xC0, 0xC1, 0xC2) and position+7 <= len(raw):
                height, width = struct.unpack('>HH', raw[position+3:position+7])
                return width, height
            position += size
    raise AdmissionError('Use a valid PNG or JPEG screenshot.', 400)


def bounded_payload(payload):
    """Bound the actual provider packet, not attacker-supplied count metadata."""
    if payload.get('model') != providers.BASETEN_MODEL or not 1 <= payload.get('max_tokens', 0) <= 6000:
        raise AdmissionError('Unsupported model configuration.', 400)
    images = 0
    text_bytes = 0
    for message in payload['messages']:
        parts = message['content']
        if isinstance(parts, str):
            text_bytes += len(parts.encode('utf-8'))
            continue
        for part in parts:
            if part['type'] == 'text':
                text_bytes += len(part['text'].encode('utf-8'))
            elif part['type'] == 'image_url':
                try:
                    value = part['image_url']['url']
                    if not re.fullmatch(r'data:image/(png|jpeg);base64,[A-Za-z0-9+/=]+', value):
                        raise ValueError()
                    raw = base64.b64decode(value.split(',', 1)[1], validate=True)
                    width, height = image_size(raw)
                    if not 0 < width <= 1536 or not 0 < height <= 1536 or width*height > 1_600_000 or len(raw) > 2*1024*1024:
                        raise ValueError()
                except (ValueError, KeyError):
                    raise AdmissionError('Trial screenshots must be PNG/JPEG, at most 1536 px per side, 1.6 megapixels and 2 MB each.', 400) from None
                images += 1
    if images > 4 or text_bytes > 40_000:
        raise AdmissionError('This trial supports up to four screenshots and 40 KB of model source text. Use a smaller export or continue manual review.', 400)


def run(route, payload, store, token, client, request_id, transport=None):
    if payload.get('consent') is not True:
        raise AdmissionError('Confirm sending this source data to Meta via Baseten first.', 400)
    if payload.get('route', 'baseten') != 'baseten':
        raise AdmissionError('The hosted trial supports Meta via Baseten only.', 400)
    project = payload.get('project')
    from .compiler import validate_workspace
    validate_workspace(project)
    if len(project['pages']) > 60:
        raise AdmissionError('Use at most 60 source pages for this AI trial.', 400)
    reservation = None
    usage = None

    def guarded(provider, url, key, packet):
        nonlocal reservation, usage
        if provider != 'Baseten' or url != providers.BASETEN_CHAT_URL or reservation:
            raise AdmissionError('Only one approved model call is allowed per operation.', 400)
        bounded_payload(packet)
        packet = {**packet, 'reasoning_effort': 'low'}
        reservation = store.reserve(token, client, request_id)
        response = (transport or providers.post_json)(provider, url, key, packet)
        usage = response.get('usage') if isinstance(response, dict) else None
        return response

    try:
        if route == '/api/enhance':
            result = providers.enhance(project, True, payload.get('screenshot'), guarded, 'baseten', configure_view=False)
        elif route == '/api/reconstruct-process':
            from .processes import reconstruct_process
            result = reconstruct_process(project, payload.get('observations'), True, guarded)
        else:
            raise AdmissionError('This hosted AI operation is not available.', 404)
        if reservation:
            store.finish(reservation, True, usage)
        result['trial'] = store.session(token, client)[1]
        return result
    except Exception:
        if reservation:
            store.finish(reservation, False, usage)
        raise
