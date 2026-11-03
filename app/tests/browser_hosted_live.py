"""Explicit opt-in: two real hosted Meta calls using synthetic new uploads."""
import csv
import io
import json
import os
from pathlib import Path
import sys
import time
import zipfile
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from exitforge.process_fixtures import process_case


def run():
    if '--live' not in sys.argv:
        print('No inference run. --live requires the existing scoped credit authorization.');return
    base=os.environ['EXITFORGE_TEST_URL'];out=Path(os.environ['EXITFORGE_TEST_EVIDENCE'])
    out.mkdir(parents=True,exist_ok=True);errors=[];calls=[]
    stream=io.BytesIO();table=io.StringIO();writer=csv.writer(table)
    writer.writerow(['Name','Status','Client']);writer.writerows([['Orion release','Review','Nova Studio'],['Luma guide','Delivered','Nova Studio']])
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('Projects.csv',table.getvalue())
        archive.writestr('Orion release.md','# Orion release\n\nNova Studio launch documentation.\n- [ ] Final approval\n- [x] Brief reviewed\n')
        archive.writestr('Luma guide.md','# Luma guide\n\nNova Studio approved documentation.\n- [x] Final approval\n')
    text_zip=out/'new-customer-export.zip';text_zip.write_bytes(stream.getvalue())
    process_zip=out/'new-linked-export.zip';process_zip.write_bytes(process_case('delivery')[2])
    with sync_playwright() as p:
        browser=p.chromium.launch();context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
        page=context.new_page();page.set_default_timeout(15000);page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(base,wait_until='networkidle');expect(page.locator('#hosted-ai-allowance')).to_contain_text('2 operation(s)')
        page.locator('#workspace-file').set_input_files(str(text_zip))
        page.get_by_role('button',name='Review with Meta AI',exact=True).click()
        expect(page.locator('#run-ai')).to_be_enabled();page.locator('#cloud-consent').check()
        if '--resume-vision' in sys.argv:
            saved=json.loads((out/'text-response.json').read_text())
            page.route('**/api/enhance',lambda route:route.fulfill(json=saved))
        started=time.monotonic()
        with page.expect_response(lambda r:r.url.endswith('/api/enhance'),timeout=120000) as event:
            page.locator('#run-ai').click()
        response=event.value;result=response.json();(out/'text-response.json').write_text(json.dumps(result,indent=2)+'\n')
        assert response.status==200,(response.status,result)
        calls.extend(result['calls']);assert len(result['calls'])==1
        expect(page.get_by_role('region',name='AI proposal')).to_be_visible()
        expect(page.locator('#confirm-rule')).not_to_be_checked()
        page.screenshot(path=str(out/'01-actual-new-text-proposal.png'),full_page=True)
        page.locator('#confirm-rule').check();page.get_by_role('button',name='Confirm & open workspace',exact=True).click()
        expect(page.locator('.project-card')).to_have_count(2)
        time.sleep(max(0,21-(time.monotonic()-started)))
        page.goto(base)
        page.locator('#workspace-file').set_input_files(str(process_zip))
        page.locator('.process-input summary').click()
        files=[str(ROOT/f'examples/process-observations/delivery/frame-{n}.png') for n in range(1,5)]
        page.locator('#process-observations').set_input_files(files);page.locator('#process-consent').check()
        with page.expect_response(lambda r:r.url.endswith('/api/reconstruct-process'),timeout=120000) as event:
            page.locator('#reconstruct-process').click()
        response=event.value;result=response.json();(out/'vision-response.json').write_text(json.dumps(result,indent=2)+'\n')
        assert response.status==200,(response.status,result)
        calls.extend(result['calls']);assert len(result['calls'])==1
        expect(page.locator('#process-parent-policy')).to_be_visible()
        expect(page.locator('#confirm-process')).not_to_be_checked()
        page.locator('#process-parent-policy').select_option('Changes requested')
        page.locator('#process-contextual-task').click()
        page.screenshot(path=str(out/'02-actual-new-vision-proposal.png'),full_page=True)
        page.locator('#confirm-process').check();page.locator('#open-process').click()
        page.locator('[data-select-project]').filter(has_text='Brand launch').click()
        page.get_by_role('button',name='Hand over',exact=True).click()
        expect(page.locator('.runtime-notice')).to_contain_text('must be Approved')
        page.locator('.linked-item').filter(has_text='Logo pack').get_by_role('button',name='Mark Approved',exact=True).click()
        page.get_by_role('button',name='Hand over',exact=True).click()
        expect(page.locator('.runtime-notice')).to_contain_text('One local receipt task')
        page.get_by_role('button',name='Take it with you',exact=True).click()
        with page.expect_download() as event:page.get_by_role('button',name='Download independent app',exact=True).click()
        artifact=out/'actual-ai-independent.html';event.value.save_as(str(artifact))
        expect(page.locator('#hosted-ai-allowance')).to_contain_text('1 operation(s)' if '--resume-vision' in sys.argv else 'reached its allowance')
        context.close()
        offline=browser.new_context(viewport={'width':390,'height':844});offline.set_offline(True)
        page=offline.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        requests=[];page.on('request',lambda r:requests.append(r.url) if r.url.startswith(('http:','https:')) else None)
        page.goto(artifact.as_uri());expect(page.locator('.linked-workspace')).to_be_visible()
        page.get_by_role('button',name='Follow-ups',exact=True).click();expect(page.locator('.task-row')).to_have_count(1)
        page.reload();expect(page.locator('.linked-workspace')).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(out/'03-actual-ai-offline-mobile.png'),full_page=True)
        assert not requests;browser.close()
    assert not errors,errors
    result={'status':'passed','url':base,'actual_new_upload_text_and_vision':True,'real_inference_calls':len(calls),
            'model_ids':[c['model'] for c in calls],'calls':calls,'human_confirmation_required':True,
            'real_linked_delivery_guard_and_receipt':True,'download_opened_offline':True,'offline_http_requests':requests,
            'session_allowance_visible':True,'text_result_replayed_without_new_call':'--resume-vision' in sys.argv,'page_errors':errors}
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':run()
