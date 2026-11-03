"""Actual linked actions, recorded model review and offline persistence; no inference."""
import json
import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from exitforge.process_fixtures import process_case
BASE=os.environ.get('EXITFORGE_TEST_URL','http://127.0.0.1:8766')
OUT=Path(os.environ.get('EXITFORGE_TEST_EVIDENCE',ROOT.parent/'.hackathon/evidence/exitforge-process-upgrade-2026-11-02/browser')).resolve()


def run():
    OUT.mkdir(parents=True,exist_ok=True);errors=[];cloud=[];offline_requests=[]
    with sync_playwright() as p:
        browser=p.chromium.launch()
        context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
        page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('request',lambda request:cloud.append(request.url) if request.url.endswith(('/api/reconstruct-process','/api/enhance','/api/modal-package')) else None)
        page.goto(BASE);page.get_by_role('button',name='Rebuild a working process').click()
        expect(page.get_by_role('region',name='Process reconstruction')).to_contain_text('RECORDED ACTUAL META RUN')
        page.locator('#confirm-process').check();page.locator('#open-process').click()
        expect(page.locator('#studio-notice')).to_contain_text('Choose what happens')
        page.locator('.process-observations summary').click()
        expect(page.locator('.observation-strip img')).to_have_count(4)
        assert page.locator('.observation-strip img').evaluate_all('(images)=>images.every(image=>image.complete&&image.naturalWidth>0)')
        page.locator('#process-parent-policy').select_option('Changes requested')
        page.screenshot(path=str(OUT/'01-review.png'),full_page=True)
        page.locator('#confirm-process').check();page.locator('#open-process').click()
        expect(page.locator('.linked-workspace')).to_have_count(1)
        page.locator('[data-select-project]').filter(has_text='Brand launch').click()
        page.get_by_role('button',name='Hand over',exact=True).click()
        expect(page.locator('.runtime-notice')).to_contain_text('Logo pack must be Approved')
        expect(page.locator('#process-readiness')).to_contain_text('blocked')
        page.screenshot(path=str(OUT/'02-linked-guard.png'),full_page=True)
        item=page.locator('.linked-item').filter(has_text='Logo pack')
        item.get_by_role('button',name='Request changes',exact=True).click()
        expect(page.locator('.process-detail-heading')).to_contain_text('Changes requested')
        expect(page.locator('.linked-item').filter(has_text='Usage guide')).to_contain_text('Approved')
        page.locator('.linked-item').filter(has_text='Logo pack').get_by_role('button',name='Mark Approved').click()
        expect(page.locator('#process-readiness')).to_contain_text('Ready')
        page.get_by_role('button',name='Hand over',exact=True).click()
        expect(page.locator('.runtime-notice')).to_contain_text('One local receipt task')
        page.get_by_role('button',name='Hand over',exact=True).click()
        page.get_by_role('button',name='Follow-ups',exact=True).click()
        expect(page.locator('.task-row')).to_have_count(1);expect(page.locator('.task-row')).to_contain_text('Northstar Studio received Brand launch')
        page.get_by_role('button',name='Projects',exact=True).click()
        page.locator('[data-select-project]').filter(has_text='Website refresh').click()
        page.get_by_role('button',name='Mark Approved').click();page.get_by_role('button',name='Hand over',exact=True).click()
        page.get_by_role('button',name='Follow-ups',exact=True).click()
        expect(page.locator('.task-row')).to_have_count(2)
        expect(page.locator('.task-row').filter(has_text='Cedar & Co')).to_contain_text('Website refresh')
        page.set_viewport_size({'width':390,'height':844})
        page.get_by_role('button',name='Projects',exact=True).click()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(OUT/'03-mobile.png'),full_page=True)
        page.get_by_role('button',name='Take it with you',exact=True).click()
        with page.expect_download() as event:page.get_by_role('button',name='Download independent app').click()
        artifact=OUT/'linked-independent.html';event.value.save_as(str(artifact));context.close()
        offline=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True);offline.set_offline(True)
        page=offline.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('request',lambda request:offline_requests.append(request.url) if request.url.startswith(('http:','https:')) else None)
        page.goto(artifact.as_uri());page.locator('[data-select-project]').filter(has_text='Brand launch').click()
        page.locator('.linked-item').filter(has_text='Logo pack').get_by_role('button',name='Request changes',exact=True).click()
        expect(page.locator('#process-readiness')).to_contain_text('Logo pack must be Approved')
        page.reload();expect(page.locator('.process-detail-heading')).to_contain_text('Changes requested')
        page.locator('.linked-item').filter(has_text='Logo pack').get_by_role('button',name='Mark Approved').click();page.get_by_role('button',name='Hand over',exact=True).click()
        page.get_by_role('button',name='Inspect source',exact=True).click()
        dialog=page.get_by_role('dialog',name='Source record')
        dialog.get_by_label('Working notes').fill('Continued the linked handoff while offline.')
        with page.expect_download() as event:dialog.get_by_role('button',name='handoff-note.txt').click()
        event.value.save_as(str(OUT/'handoff-note.txt'))
        dialog.get_by_role('button',name='Save notes').click();page.reload()
        with page.expect_download() as event:page.get_by_role('button',name='Data backup',exact=True).click()
        event.value.save_as(str(OUT/'current-backup.json'))
        data=json.loads((OUT/'current-backup.json').read_text(encoding='utf-8'))
        assert len(data['tasks'])==2 and data['process']['confirmed'] is True
        assert any('while offline' in record['body'] for record in data['pages'])
        assert data['process_review']['proposal'].get('confirmed',False) is False
        with page.expect_download() as event:page.get_by_role('button',name='Application',exact=True).click()
        fresh=OUT/'reexported.html';event.value.save_as(str(fresh))
        page.screenshot(path=str(OUT/'04-independent-offline.png'),full_page=True)
        offline.close()
        fresh_context=browser.new_context();fresh_context.set_offline(True);page=fresh_context.new_page();page.goto(fresh.as_uri())
        page.get_by_role('button',name='Follow-ups',exact=True).click();expect(page.locator('.task-row')).to_have_count(2);fresh_context.close()
        # Different schema and the real model's unsupported task placeholders.
        context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True);page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(BASE);page.locator('#workspace-file').set_input_files(str(ROOT/'examples/process-editorial.json'))
        page.locator('#process-parent-policy').select_option('Revision');page.locator('#confirm-process').check();page.locator('#open-process').click()
        expect(page.locator('#studio-notice')).to_contain_text('reusable')
        page.get_by_role('button',name='Use contextual receipt task').click();expect(page.locator('#confirm-process')).not_to_be_checked()
        page.locator('#confirm-process').check();page.locator('#open-process').click()
        page.locator('[data-select-project]').filter(has_text='Autumn issue').click()
        page.locator('.linked-item').filter(has_text='Feature article').get_by_role('button',name='Mark Accepted').click();page.get_by_role('button',name='Hand over',exact=True).click()
        expect(page.locator('.process-detail-heading')).to_contain_text('Released')
        page.screenshot(path=str(OUT/'05-editorial-domain.png'),full_page=True)
        context.close()
        # Exercise the user's ZIP + screenshots path with a recorded response;
        # the local endpoint is intercepted, so this makes no paid request.
        context=browser.new_context(viewport={'width':1440,'height':1000});page=context.new_page()
        page.on('pageerror',lambda error:errors.append(str(error)))
        example=json.loads((ROOT/'examples/process-delivery.json').read_text(encoding='utf-8'))
        review=example['process_review'];requests=[]
        def recorded_response(route):
            payload=route.request.post_data_json;requests.append(payload)
            assert payload['consent'] is True and len(payload['observations'])==4
            assert not payload['project'].get('process')
            route.fulfill(status=200,content_type='application/json',body=json.dumps({'process':example['process'],'observations':review['observations'],'calls':review['calls'],'question':review.get('question','Choose the parent change-request policy.')}))
        page.route('**/api/reconstruct-process',recorded_response)
        page.goto(BASE)
        archive=OUT/'own-input.zip';archive.write_bytes(process_case('delivery')[2])
        observations=ROOT/'examples/process-observations/delivery'
        page.locator('#workspace-file').set_input_files(str(archive))
        page.locator('.process-input summary').click()
        page.locator('#reconstruct-process').click();expect(page.locator('#studio-notice')).to_contain_text('Confirm the screenshot')
        page.locator('#process-consent').check()
        page.locator('#process-observations').set_input_files([str(observations/f'frame-{i}.png') for i in range(1,5)])
        expect(page.locator('#process-consent')).not_to_be_checked()
        page.locator('#process-consent').check();page.locator('#reconstruct-process').click()
        expect(page.locator('#process-parent-policy')).to_be_visible();assert len(requests)==1
        expect(page.locator('#confirm-process')).not_to_be_checked()
        page.locator('#process-parent-policy').select_option('Changes requested');page.locator('#confirm-process').check();page.locator('#open-process').click()
        expect(page.locator('.linked-workspace')).to_have_count(1)
        context.close();browser.close()
    assert not errors and not cloud and not offline_requests,(errors,cloud,offline_requests)
    result={'status':'passed','actual_recorded_vision_output_reviewed':True,'new_live_provider_calls':0,'linked_guard':True,'revision_branch':True,'two_client_receipts':2,'editorial_schema_and_task_correction':True,'own_zip_and_screenshot_ui_with_intercepted_response':True,'offline_notes_actions_reload_backup_reexport':True,'mobile_no_overflow':True,'errors':errors,'offline_http_requests':offline_requests}
    (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))


if __name__=='__main__':run()
