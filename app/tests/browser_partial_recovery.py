"""Real local HTTP/UI with an injected provider failure; zero live API calls."""
import json
import os
from pathlib import Path
import sys
import threading
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from exitforge.server import Handler
from exitforge.providers import enhance, ProviderFailure
from exitforge.importer import recover_archive
from exitforge.sample import sample_archive

EVIDENCE=Path(os.environ.get('EXITFORGE_TEST_EVIDENCE',ROOT.parent/'.hackathon/evidence/exitforge-partial-recovery-2026-11-02')).resolve()


def run():
    EVIDENCE.mkdir(parents=True,exist_ok=True)
    provider_calls=[];errors=[];cloud_posts=[];offline_http=[]
    project=recover_archive(sample_archive('client-handoff'))
    project['provenance']['sample']=True
    project['presentation']={'primary_view':'docs','database_id':project['databases'][0]['id']}
    fixture=EVIDENCE/'input.json';fixture.write_text(json.dumps(project),encoding='utf-8')
    def fail_view(provider,url,key,payload):
        provider_calls.append({'provider':provider,'operation':'interpret' if len(provider_calls)==0 else 'configure_view'})
        if len(provider_calls)>1:raise ProviderFailure('Test-only simulated view failure.')
        spec={'workspace_name':'AI handoff proposal','status_field':'Status',
              'states':['In progress','Review','Delivered'],'delivery_state':'Delivered',
              'followup':'Confirm {client} received {project}.','require_checklist':True,
              'rationale':'Retain source handoff stages and client context.',
              'evidence_sources':[project['databases'][0]['source']],
              'unknowns':['Original access permissions are not in the export.']}
        return {'choices':[{'message':{'content':json.dumps(spec)}}],'usage':{'total_tokens':123}}
    def local_enhance(project,consent,screenshot,route):
        return enhance(project,consent,screenshot,transport=fail_view,route=route)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        with patch.dict(os.environ,{'EXITFORGE_ALLOW_CLOUD':'1','BASETEN_API_KEY':'test-only-no-network'}),patch('exitforge.server.enhance',local_enhance),sync_playwright() as p:
            browser=p.chromium.launch()
            context=browser.new_context(viewport={'width':390,'height':844},accept_downloads=True)
            page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('request',lambda r:cloud_posts.append(r.url) if r.url.endswith('/api/enhance') else None)
            page.goto(f'http://127.0.0.1:{server.server_port}')
            page.locator('#workspace-file').set_input_files(str(fixture))
            page.locator('.cloud-options>summary').click()
            page.locator('#cloud-consent').check()
            page.get_by_role('button',name='Interpret workflow',exact=False).click()
            expect(page.get_by_role('region',name='AI proposal')).to_contain_text('setup incomplete')
            expect(page.get_by_role('region',name='AI proposal')).to_contain_text('configure_view · failed')
            expect(page.locator('#workspace-name')).to_have_value('AI handoff proposal')
            expect(page.locator('#confirm-rule')).not_to_be_checked()
            expect(page.locator('#cloud-consent')).not_to_be_checked()
            assert len(provider_calls)==2
            page.screenshot(path=str(EVIDENCE/'01-partial-proposal-mobile.png'),full_page=True)
            page.locator('.partial-recovery').screenshot(path=str(EVIDENCE/'03-incomplete-setup-card.png'))
            page.get_by_role('button',name='Interpret again',exact=False).click()
            expect(page.locator('#studio-notice')).to_contain_text('Confirm the cloud-data operation')
            assert len(provider_calls)==2 and len(cloud_posts)==1
            page.reload();page.get_by_role('button',name='Resume saved workspace',exact=True).click()
            expect(page.get_by_role('region',name='AI proposal')).to_contain_text('setup incomplete')
            expect(page.locator('#cloud-consent')).not_to_be_checked()
            page.get_by_role('button',name='Continue manual review',exact=False).click()
            expect(page.locator('#confirm-rule')).to_be_focused()
            expect(page.locator('#confirm-rule')).not_to_be_checked()
            page.locator('#followup-text').fill('Confirm {client} received {project}.')
            page.locator('#confirm-rule').check()
            page.get_by_role('button',name='Confirm & open workspace',exact=False).click()
            # Preserve the previous validated Documents view when the model has no replacement.
            expect(page.locator('[data-view="docs"]')).to_have_attribute('aria-current','page')
            page.get_by_role('button',name='Projects',exact=False).click()
            page.locator('.project-card').filter(has=page.locator('strong',has_text='Brand launch')).click()
            dialog=page.get_by_role('dialog',name='Project details')
            dialog.get_by_label('Project status').select_option('Delivered')
            expect(dialog.locator('.dialog-message')).to_contain_text('Complete the handoff checklist')
            for item in dialog.locator('[data-check]').all():item.check()
            dialog.get_by_label('Project status').select_option('Delivered')
            dialog.get_by_role('button',name='Close project details').click()
            page.get_by_role('button',name='Take it with you',exact=False).click()
            with page.expect_download() as event:page.get_by_role('button',name='Download independent app',exact=False).click()
            artifact=EVIDENCE/'partial-independent.html';event.value.save_as(str(artifact))
            context.close()
            offline=browser.new_context(viewport={'width':390,'height':844},accept_downloads=True)
            offline.set_offline(True);page=offline.new_page()
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('request',lambda r:offline_http.append(r.url) if r.url.startswith(('http:','https:')) else None)
            page.goto(artifact.as_uri());page.get_by_role('button',name='Follow-ups',exact=False).click()
            expect(page.locator('.task-row')).to_contain_text('Northstar Studio received Brand launch')
            page.locator('[data-task]').check();page.reload()
            page.get_by_role('button',name='Follow-ups',exact=False).click()
            expect(page.locator('[data-task]')).to_be_checked()
            with page.expect_download() as event:page.get_by_role('button',name='Data backup',exact=True).click()
            backup=EVIDENCE/'partial-current-backup.json';event.value.save_as(str(backup))
            data=json.loads(backup.read_text(encoding='utf-8'))
            assert data['ai_review']['outcome']=='partial' and data['presentation']['primary_view']=='docs'
            assert data['ai_review']['presentation'] is None and data['workflow']['confirmed']
            assert len(data['provenance']['cloud_calls'])==2
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.screenshot(path=str(EVIDENCE/'02-offline-continuation.png'),full_page=True)
            offline.close();browser.close()
    finally:
        server.shutdown();server.server_close();thread.join()
    assert len(provider_calls)==2 and len(cloud_posts)==1 and not errors and not offline_http
    result={'status':'passed','injected_provider_calls':provider_calls,'live_api_calls':0,
            'partial_result_persisted':True,'manual_continuation_without_extra_calls':True,
            'fresh_consent_required':True,'previous_view_preserved':True,'offline_edit_reload_backup':True,
            'errors':errors,'offline_http_requests':offline_http}
    (EVIDENCE/'browser-partial-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':run()
