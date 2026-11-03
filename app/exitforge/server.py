"""Loopback-only recovery studio. No source files or secrets are written by requests."""

import argparse
import base64
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from .compiler import STATIC, compile_application, validate_workspace
from .importer import ImportFailure, recover_archive
from .providers import ProviderFailure, enhance, package_with_modal, status
from .sample import sample_archive

STATIC_ROUTES={'/':('index.html','text/html; charset=utf-8'),
               '/process.js':('process.js','text/javascript; charset=utf-8'),
               '/process-ui.js':('process-ui.js','text/javascript; charset=utf-8'),
               '/process-records.js':('process-records.js','text/javascript; charset=utf-8'),
               '/process-record-form.js':('process-record-form.js','text/javascript; charset=utf-8'),
               '/handoff.js':('handoff.js','text/javascript; charset=utf-8'),
               '/handoff-view.js':('handoff-view.js','text/javascript; charset=utf-8'),
               '/process-studio.js':('process-studio.js','text/javascript; charset=utf-8'),
               '/style.css':('style.css','text/css; charset=utf-8'),
               '/studio.js':('studio.js','text/javascript; charset=utf-8'),
               '/workspace.js':('workspace.js','text/javascript; charset=utf-8'),
               '/runtime.js':('runtime.js','text/javascript; charset=utf-8')}


class Handler(BaseHTTPRequestHandler):
    server_version='ExitForge/0.1'

    def _allowed_host(self):
        expected={f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
        return self.headers.get('Host') in expected

    def _allowed_origins(self):
        return {f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'}

    def _public_demo(self):
        return os.getenv('EXITFORGE_DEPLOYMENT_MODE')=='public-demo'

    def _provider_status(self):
        result=status()
        if self._public_demo():
            result['cloud_enabled']=False
            for provider in result['providers']:provider['configured']=False
            result['deployment']={'mode':'public-demo','notice':'Live cloud operations are disabled on this public demo. Saved actual Meta examples remain available.'}
        return result

    def _read_input(self,length):
        self.connection.settimeout(30)
        return self.rfile.read(length)

    def _send(self,code,data,mime='application/json; charset=utf-8',filename=None):
        if isinstance(data,dict):data=json.dumps(data).encode('utf-8')
        elif isinstance(data,str):data=data.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type',mime)
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        if filename:self.send_header('Content-Disposition',f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self._allowed_host():return self._send(403,{'error':'Loopback access only.'})
        path=urlsplit(self.path).path
        if path in STATIC_ROUTES:
            filename,mime=STATIC_ROUTES[path]
            return self._send(200,(STATIC/filename).read_bytes(),mime)
        if path=='/api/status':return self._send(200,self._provider_status())
        if path=='/api/meta-example':
            project=json.loads((STATIC.parent/'examples/meta-localization.json').read_text(encoding='utf-8'))
            return self._send(200,validate_workspace(project))
        if path=='/api/process-example':
            domain=parse_qs(urlsplit(self.path).query).get('domain',['delivery'])[0]
            if domain not in ('delivery','editorial'):return self._send(400,{'error':'Unknown process example.'})
            return self._send(200,validate_workspace(json.loads((STATIC.parent/f'examples/process-{domain}.json').read_text(encoding='utf-8'))))
        if path.startswith('/process-example/'):
            import re
            match=re.fullmatch(r'/process-example/(delivery|editorial)/(frame-[1-4]\.png)',path)
            if match:return self._send(200,(STATIC.parent/'examples/process-observations'/match[1]/match[2]).read_bytes(),'image/png')
        if path in ('/api/sample','/api/sample.zip'):
            scenario=parse_qs(urlsplit(self.path).query).get('scenario',['studio'])[0]
            if scenario not in ('studio','client-handoff'):
                return self._send(400,{'error':'Unknown sample scenario.'})
            filename='client-handoff-demo.zip' if scenario=='client-handoff' else 'Northstar workspace.zip'
            archive=sample_archive(scenario)
            if path=='/api/sample.zip':
                return self._send(200,archive,'application/zip',filename)
            # JSON keeps an in-app sample request separate from an attachment download.
            return self._send(200,{'filename':filename,'archive_base64':base64.b64encode(archive).decode('ascii')})
        if path=='/favicon.ico':return self._send(204,b'','image/x-icon')
        return self._send(404,{'error':'Not found.'})

    def do_POST(self):
        if not self._allowed_host() or self.headers.get('X-ExitForge')!='studio-v1':
            return self._send(403,{'error':'Only the local recovery studio may make this request.'})
        origin=self.headers.get('Origin')
        if origin and origin not in self._allowed_origins():
            return self._send(403,{'error':'Cross-origin requests are not allowed.'})
        if self._public_demo() and urlsplit(self.path).path in {'/api/enhance','/api/reconstruct-process','/api/modal-package'}:
            return self._send(409,{'error':'Live cloud operations are disabled on this public demo. Use a saved Meta example or continue manual review.'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if length<=0:raise ValueError('The input is empty. Choose a non-empty ZIP or JSON backup.')
            if length>20*1024*1024:raise ValueError('Choose an input smaller than 20 MB.')
            raw=self._read_input(length)
            if len(raw)!=length:raise ValueError('Incomplete input.')
            path=urlsplit(self.path).path
            if path=='/api/import':
                filename=unquote(self.headers.get('X-Filename','workspace.zip'))[:200]
                return self._send(200,recover_archive(raw,filename))
            payload=json.loads(raw)
            project=validate_workspace(payload.get('project'))
            if path=='/api/validate':
                return self._send(200,project)
            if path=='/api/package':
                return self._send(200,compile_application(project),'text/html; charset=utf-8','independent-workspace.html')
            if path=='/api/enhance':
                return self._send(200,enhance(project,payload.get('consent'),payload.get('screenshot'),route=payload.get('route','direct')))
            if path=='/api/reconstruct-process':
                from .processes import reconstruct_process
                return self._send(200,reconstruct_process(project,payload.get('observations'),payload.get('consent')))
            if path=='/api/modal-package':
                return self._send(200,package_with_modal(project,payload.get('consent')),'text/html; charset=utf-8','independent-workspace.html')
            return self._send(404,{'error':'Not found.'})
        except ProviderFailure as exc:
            return self._send(409,{'error':str(exc)})
        except (ImportFailure,ValueError,UnicodeError,TypeError,AttributeError) as exc:
            message=str(exc) if isinstance(exc,(ImportFailure,ValueError)) and not isinstance(exc,json.JSONDecodeError) else 'The input format is invalid.'
            return self._send(400,{'error':message[:250]})
        except Exception:
            return self._send(500,{'error':'The operation could not complete. Your original export was not changed.'})

    def log_message(self,format,*args):
        # Do not log paths, input records, request bodies or provider messages.
        pass


def load_local_env():
    path=Path(__file__).resolve().parent.parent/'.env'
    if not path.exists():return
    for line in path.read_text(encoding='utf-8').splitlines():
        line=line.strip()
        if not line or line.startswith('#') or '=' not in line:continue
        key,value=line.split('=',1)
        if key.strip().isidentifier():os.environ.setdefault(key.strip(),value.strip().strip('"').strip("'"))


def main():
    parser=argparse.ArgumentParser(description='Run the ExitForge local recovery studio.')
    parser.add_argument('--port',type=int,default=8765)
    options=parser.parse_args()
    load_local_env()
    server=ThreadingHTTPServer(('127.0.0.1',options.port),Handler)
    print(f'ExitForge studio: http://127.0.0.1:{server.server_port}',flush=True)
    print('Local recovery is available. Cloud calls require explicit configuration and consent.',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=='__main__':main()
