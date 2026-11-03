"""Real source resolver plus isolated fake model transport; never paid inference."""
import base64
import copy
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch
from playwright.sync_api import sync_playwright,expect

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from exitforge.process_bindings import source_bindings
from exitforge.process_fixtures import process_case
from exitforge.processes import reconstruct_process

BASE=os.environ.get('EXITFORGE_TEST_URL','http://127.0.0.1:8766')
OUT=Path(os.environ['EXITFORGE_TEST_EVIDENCE'])


def run():
    OUT.mkdir(parents=True,exist_ok=True)
    project,spec,archive,_=process_case();binding=source_bindings(project)[0]
    proposal={k:copy.deepcopy(v) for k,v in spec.items() if k not in ('parent_db','child_db','parent_states','child_states','links')}
    proposal['binding_id']=binding['id']
    files=[ROOT/f'examples/process-observations/delivery/frame-{i}.png' for i in range(1,5)]
    frames=[{'data_url':'data:image/png;base64,'+base64.b64encode(f.read_bytes()).decode()} for f in files]
    with patch.dict(os.environ,{'EXITFORGE_ALLOW_CLOUD':'1','BASETEN_HACKATHON_API_KEY':'test-only-unused'}):
        response=reconstruct_process(project,frames,True,lambda *args:{'choices':[{'message':{'content':json.dumps(proposal)}}]})
    (OUT/'source.zip').write_bytes(archive);errors=[];requests=[]
    with sync_playwright() as p:
        browser=p.chromium.launch();context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
        page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        page.route('**/api/reconstruct-process',lambda route:route.fulfill(json=response))
        page.goto(BASE);page.locator('#workspace-file').set_input_files(str(OUT/'source.zip'))
        page.locator('.process-input summary').click();page.locator('#process-observations').set_input_files([str(f) for f in files])
        page.locator('#process-consent').check();page.locator('#reconstruct-process').click()
        coverage=page.get_by_role('region',name='Source relationship coverage')
        expect(coverage).to_contain_text('4 relationships resolved from explicit export links')
        coverage.locator('summary').click();expect(coverage.locator('pre')).to_contain_text(binding['id'])
        expect(page.locator('#confirm-process')).not_to_be_checked()
        with page.expect_download() as event:page.locator('#process-review-receipt').click()
        receipt_path=OUT/'receipt.json';event.value.save_as(str(receipt_path))
        receipt=json.loads(receipt_path.read_text());history=receipt['linked_process']['original_proposal']
        assert history['model_proposal']==proposal
        assert len(history['proposal']['links'])==4 and history['binding_resolution']['relationship_count']==4
        page.locator('#process-parent-policy').select_option('Changes requested');page.locator('#confirm-process').check();page.locator('#open-process').click()
        page.locator('[data-select-project]').filter(has_text='Brand launch').click()
        page.get_by_role('button',name='Hand over',exact=True).click();expect(page.locator('.runtime-notice')).to_contain_text('must be Approved')
        page.locator('.linked-item').filter(has_text='Logo pack').get_by_role('button',name='Mark Approved',exact=True).click()
        page.get_by_role('button',name='Hand over',exact=True).click();expect(page.locator('.runtime-notice')).to_contain_text('One local receipt task')
        page.screenshot(path=str(OUT/'source-bound-handover.png'),full_page=True)
        page.get_by_role('button',name='Take it with you',exact=True).click()
        with page.expect_download() as event:page.get_by_role('button',name='Download independent app',exact=True).click()
        artifact=OUT/'independent.html';event.value.save_as(str(artifact));context.close()
        offline=browser.new_context(viewport={'width':390,'height':844});offline.set_offline(True);page=offline.new_page()
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda r:requests.append(r.url) if r.url.startswith(('http:','https:')) else None)
        page.goto(artifact.as_uri());page.get_by_role('button',name='Follow-ups',exact=True).click();expect(page.locator('.task-row')).to_have_count(1)
        page.reload();expect(page.locator('.linked-workspace')).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(OUT/'offline.png'),full_page=True);browser.close()
    assert not errors and not requests,(errors,requests)
    result={'status':'passed','real_source_resolver':True,'model_response_intercepted':True,'new_paid_calls':0,
            'complete_source_graph':4,'raw_compact_proposal_and_binding_provenance_in_receipt':True,'explicit_confirmation':True,
            'real_runtime_guard_and_task':True,'actual_download_offline_reload':True,'page_errors':errors,'offline_http_requests':requests}
    (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':run()
