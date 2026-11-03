"""Bounded public transport; shared recovery routes retain their local adapter."""
import asyncio
from email.message import Message
from http.cookies import SimpleCookie, CookieError
import json
import os
from pathlib import Path
import sqlite3
from types import SimpleNamespace
from urllib.parse import urlsplit

from .server import Handler
from . import public_ai

MAX_INPUT=20*1024*1024
MAX_OUTPUT=32*1024*1024
gate=asyncio.Semaphore(2)
NOTICE='VPS demo: ZIP import and application packaging send data to this server. Drafts stay in this browser. AI uses Meta via Baseten only after your consent, subject to the shared trial allowance.'


def public_origin():
    path=os.getenv('EXITFORGE_PUBLIC_ORIGIN_FILE')
    try:value=Path(path).read_text(encoding='utf-8').strip() if path else os.getenv('EXITFORGE_PUBLIC_ORIGIN','')
    except OSError:return ''
    try:
        parsed=urlsplit(value)
        if (len(value)>300 or parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.path not in ('','/') or parsed.query or parsed.fragment or parsed.port not in (None,443)):
            return ''
        host=parsed.hostname.encode('idna').decode('ascii').lower()
        if any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789.-' for c in host):return ''
        return 'https://'+host
    except (ValueError,UnicodeError):return ''


class PublicRequest(Handler):
    """Reuse application routing, replacing socket I/O with ASGI request bytes."""
    def __init__(self,scope,body,origin):
        self.headers=Message()
        for key,value in scope['headers']:self.headers[key.decode('latin-1')]=value.decode('latin-1')
        self.path=scope.get('raw_path',scope['path'].encode()).decode('ascii','surrogateescape')
        if scope.get('query_string'):self.path+='?'+scope['query_string'].decode('ascii','surrogateescape')
        self.server=SimpleNamespace(server_port=scope.get('server',('127.0.0.1',8000))[1])
        self.body=body;self.origin=origin;self.response=None;self.scope=scope;self.extra_headers=[]

    def _allowed_host(self):
        hosts={f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
        port=os.getenv('EXITFORGE_LOOPBACK_PORT','8766')
        if port.isdigit():hosts|={f'127.0.0.1:{port}',f'localhost:{port}'}
        if self.origin:hosts|={urlsplit(self.origin).netloc,urlsplit(self.origin).netloc+':443'}
        return len(self.headers.get_all('Host',[]))==1 and self.headers.get('Host','').lower() in hosts

    def _allowed_origins(self):
        return {self.origin} if self.origin else set()

    def _public_demo(self):return True

    def _read_input(self,length):return self.body

    def _ai_context(self):
        store=public_ai.ledger()
        client=store.client(public_ai.client_address(self.scope,self.headers))
        cookie=SimpleCookie()
        try:cookie.load(self.headers.get('Cookie',''))
        except CookieError:pass
        token=cookie[public_ai.COOKIE].value if public_ai.COOKIE in cookie else ''
        return store,client,token

    def _provider_status(self):
        result=super()._provider_status()
        result['deployment']['mode']='public-demo'
        result['available_routes']=[]
        result['trial']={'available':False,'remaining':0}
        try:
            store=public_ai.ledger();remaining=store.remaining_global()
            result['cloud_enabled']=remaining>0
            result['trial']={'available':remaining>0,'shared_operations_remaining':remaining,'session_limit':2,'network_daily_limit':3}
            result['available_routes']=['baseten']
            for provider in result['providers']:
                if provider['name']=='Baseten':provider['configured']=True
            result['deployment']['notice']='Meta via Baseten is connected. AI requires consent and limited trial allowance. Direct Meta API, Fireworks and Modal are unavailable here.'
        except (public_ai.AdmissionError,sqlite3.Error,OSError):
            result['deployment']['notice']='Hosted AI is unavailable. Manual review, saved examples and independent exports remain available.'
        return result

    def do_GET(self):
        if urlsplit(self.path).path!='/api/ai/session':return super().do_GET()
        try:
            store,client,previous=self._ai_context()
            token,quota=store.session(previous,client)
            self.extra_headers.append((b'set-cookie',f'{public_ai.COOKIE}={token}; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age=86400'.encode()))
            self._send(200,quota)
        except public_ai.AdmissionError as exc:self._send(exc.code,{'error':str(exc)})
        except (sqlite3.Error,OSError):self._send(503,{'error':'AI allowance storage is unavailable. No model call was made.'})

    def do_POST(self):
        path=urlsplit(self.path).path
        if path not in {'/api/enhance','/api/reconstruct-process'}:return super().do_POST()
        if not public_ai.configured():return super().do_POST()
        if self.headers.get('Origin')!=self.origin or not self.origin:
            return self._send(403,{'error':'Use the same-origin application to request AI.'})
        try:
            payload=json.loads(self.body)
            if not isinstance(payload,dict):raise ValueError('Use a valid AI request.')
            store,client,token=self._ai_context()
            result=public_ai.run(path,payload,store,token,client,self.headers.get('Idempotency-Key',''))
            self._send(200,result)
        except public_ai.AdmissionError as exc:self._send(exc.code,{'error':str(exc)})
        except public_ai.providers.ProviderFailure as exc:self._send(409,{'error':str(exc)+' No automatic retry was made. An attempted call uses trial allowance; your source remains available.'})
        except (sqlite3.Error,OSError):self._send(503,{'error':'AI allowance storage is unavailable. No automatic retry was made.'})
        except (ValueError,TypeError,KeyError):self._send(400,{'error':'The AI input is invalid. Review the source and consent before trying again.'})
        except Exception:self._send(500,{'error':'AI could not complete. No automatic retry was made. Your source remains available.'})

    def _send(self,code,data,mime='application/json; charset=utf-8',filename=None):
        if isinstance(data,dict):data=json.dumps(data).encode('utf-8')
        elif isinstance(data,str):data=data.encode('utf-8')
        if urlsplit(self.path).path=='/' and code==200:
            data=data.replace(b'<body>',b'<body><div class="deployment-banner" role="note">'+NOTICE.encode()+b'</div>',1)
        if len(data)>MAX_OUTPUT:code,data,mime=413,b'{"error":"The generated response is too large."}','application/json'
        headers=[(b'content-type',mime.encode()),(b'content-length',str(len(data)).encode()),(b'cache-control',b'no-store'),
          (b'x-content-type-options',b'nosniff'),(b'referrer-policy',b'no-referrer'),
          (b'content-security-policy',b"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")]
        if filename:headers.append((b'content-disposition',f'attachment; filename="{filename}"'.encode()))
        headers.extend(self.extra_headers)
        self.response=(code,headers,data)


async def app(scope,receive,send):
    if scope['type']=='lifespan':
        while True:
            event=await receive()
            if event['type']=='lifespan.startup':await send({'type':'lifespan.startup.complete'})
            elif event['type']=='lifespan.shutdown':
                await send({'type':'lifespan.shutdown.complete'});return
    if scope['type']!='http':return
    request=PublicRequest(scope,b'',public_origin());method=scope['method']
    origin_values=request.headers.get_all('Origin',[])
    if not request._allowed_host() or len(origin_values)>1 or (origin_values and origin_values[0] not in request._allowed_origins()):
        request._send(403,{'error':'Host or origin is not allowed.'})
    elif method not in {'GET','POST','HEAD'}:
        request._send(405,{'error':'Method not allowed.'})
    elif scope['path']=='/healthz' and method in {'GET','HEAD'}:
        request._send(200,{'ok':True,'mode':'public-demo','release':os.getenv('EXITFORGE_RELEASE','development')})
    elif method=='POST':
        if request.headers.get('X-ExitForge')!='studio-v1':request._send(403,{'error':'Use the recovery studio.'})
        elif len(request.headers.get_all('Content-Length',[]))>1:request._send(400,{'error':'Invalid request framing.'})
        else:
            try:
                declared=request.headers.get('Content-Length');length=int(declared) if declared is not None else None
                if length is not None and (length<0 or length>MAX_INPUT):raise ValueError('Request exceeds the 20 MB limit.')
                chunks=[];received=0
                async with asyncio.timeout(30):
                    while True:
                        event=await receive()
                        if event['type']=='http.disconnect':return
                        block=event.get('body',b'');received+=len(block)
                        if received>MAX_INPUT:raise ValueError('Request exceeds the 20 MB limit.')
                        chunks.append(block)
                        if not event.get('more_body'):break
                if length is not None and received!=length:raise ValueError('Incomplete input.')
                request.body=b''.join(chunks)
                del request.headers['Content-Length'];request.headers['Content-Length']=str(received)
                async with gate:await asyncio.to_thread(request.do_POST)
            except TimeoutError:request._send(408,{'error':'The upload timed out.'})
            except ValueError as exc:request._send(413 if 'limit' in str(exc) else 400,{'error':str(exc)})
    else:
        async with gate:await asyncio.to_thread(request.do_GET)
    if request.response is None:request._send(500,{'error':'The request could not complete.'})
    code,headers,body=request.response
    await send({'type':'http.response.start','status':code,'headers':headers})
    await send({'type':'http.response.body','body':b'' if method=='HEAD' else body})
