"""Actual local creation/editing and independent continuation; no provider call."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
BASE=os.environ.get('EXITFORGE_TEST_URL','http://127.0.0.1:8766')
OUT=Path(os.environ.get('EXITFORGE_TEST_EVIDENCE',ROOT.parent/'.hackathon/evidence/exitforge-continuation-2026-11-02/browser')).resolve()


def run():
    OUT.mkdir(parents=True,exist_ok=True);errors=[];cloud=[];offline_requests=[]
    with sync_playwright() as p:
        browser=p.chromium.launch();context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
        page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('request',lambda request:cloud.append(request.url) if request.url.endswith(('/api/enhance','/api/reconstruct-process','/api/modal-package')) else None)
        page.goto(BASE);page.get_by_role('button',name='Rebuild a working process').click()
        page.locator('#process-parent-policy').select_option('Changes requested');page.locator('#confirm-process').check();page.locator('#open-process').click()
        expect(page.get_by_role('button',name='New project',exact=True)).to_be_visible()
        page.get_by_role('button',name='New project',exact=True).click()
        dialog=page.get_by_role('dialog',name='Create project')
        dialog.get_by_role('button',name='Create project',exact=True).click()
        expect(dialog.locator('[role=alert]')).to_contain_text('name')
        dialog.get_by_label('Project name',exact=True).fill('Spring campaign')
        dialog.get_by_label('Client',exact=True).fill('Atlas Design')
        dialog.get_by_label('Initial stage',exact=True).select_option('In progress')
        dialog.get_by_label('Working notes',exact=True).fill('Created after leaving the original workspace.')
        dialog.get_by_role('button',name='Create project',exact=True).click()
        expect(page.locator('.process-detail-heading')).to_contain_text('Spring campaign')
        expect(page.locator('#process-readiness')).to_contain_text('No linked items')
        page.get_by_role('button',name='Add item',exact=True).click();dialog=page.get_by_role('dialog',name='Create linked item')
        dialog.get_by_label('Item name',exact=True).fill('Campaign artwork')
        dialog.get_by_label('Initial stage',exact=True).select_option('Draft')
        dialog.get_by_role('button',name='Create item',exact=True).click()
        expect(page.locator('.linked-item')).to_have_count(1)
        page.get_by_role('button',name='Edit project',exact=True).click();dialog=page.get_by_role('dialog',name='Edit record')
        dialog.get_by_label('Record name',exact=True).fill('Spring campaign v2')
        dialog.get_by_label('Client',exact=True).fill('Atlas Collective')
        assert dialog.locator('select').count()==0
        dialog.get_by_role('button',name='Save record',exact=True).click()
        page.get_by_role('button',name='Hand over',exact=True).click()
        expect(page.locator('.runtime-notice')).to_contain_text('Campaign artwork must be Approved')
        page.get_by_role('button',name='Mark Approved',exact=True).click();page.get_by_role('button',name='Hand over',exact=True).click()
        expect(page.get_by_role('button',name='Add item',exact=True)).not_to_be_enabled()
        page.get_by_role('button',name='Follow-ups',exact=True).click()
        expect(page.locator('.task-row')).to_contain_text('Atlas Collective received Spring campaign v2')
        page.get_by_role('button',name='Projects',exact=True).click()
        page.set_viewport_size({'width':390,'height':844});page.get_by_role('button',name='Edit project',exact=True).click()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(OUT/'01-mobile-edit.png'))
        page.get_by_role('dialog',name='Edit record').get_by_role('button',name='Cancel',exact=True).click()
        page.set_viewport_size({'width':1440,'height':1000});page.screenshot(path=str(OUT/'02-local-created-work.png'),full_page=True)
        page.get_by_role('button',name='Take it with you',exact=True).click()
        with page.expect_download() as event:page.get_by_role('button',name='Download independent app').click()
        artifact=OUT/'continuation.html';event.value.save_as(str(artifact));context.close()
        context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True);context.set_offline(True)
        page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('request',lambda request:offline_requests.append(request.url) if request.url.startswith(('http:','https:')) else None)
        page.goto(artifact.as_uri());page.locator('[data-select-project]').filter(has_text='Website refresh').click()
        page.get_by_role('button',name='Add item',exact=True).click();dialog=page.get_by_role('dialog',name='Create linked item')
        dialog.get_by_label('Item name',exact=True).fill('Mobile layout')
        dialog.get_by_label('Initial stage',exact=True).select_option('Draft');dialog.get_by_role('button',name='Create item',exact=True).click()
        page.reload();page.locator('[data-select-project]').filter(has_text='Website refresh').click()
        expect(page.locator('.linked-item')).to_have_count(2)
        item=page.locator('.linked-item').filter(has_text='Mobile layout');item.get_by_role('button',name='Edit item',exact=True).click()
        dialog=page.get_by_role('dialog',name='Edit record');dialog.get_by_label('Record name',exact=True).fill('Mobile layout - final')
        dialog.get_by_label('Working notes',exact=True).fill('Designed entirely in the independent application. <script>window.CONTINUATION_INJECTED=true</script>')
        dialog.get_by_role('button',name='Save record',exact=True).click();page.reload()
        page.locator('[data-select-project]').filter(has_text='Website refresh').click()
        expect(page.locator('.linked-item').filter(has_text='Mobile layout - final')).to_have_count(1)
        assert page.evaluate('typeof window.CONTINUATION_INJECTED')=='undefined'
        page.get_by_role('button',name='Mark Approved',exact=True).all()[0].click()
        page.get_by_role('button',name='Mark Approved',exact=True).all()[1].click();page.get_by_role('button',name='Hand over',exact=True).click()
        with page.expect_download() as event:page.get_by_role('button',name='Data backup',exact=True).click()
        backup=OUT/'current-backup.json';event.value.save_as(str(backup));data=json.loads(backup.read_text(encoding='utf-8'))
        assert len(data['tasks'])==2 and len([r for r in data['pages'] if 'local_record' in r])==3
        assert len(data['process_review']['proposal']['links'])==4 and len(data['process']['links'])==6
        original=json.loads((ROOT/'examples/process-delivery.json').read_text(encoding='utf-8'))
        assert data['process_review']['proposal']==original['process_review']['proposal']
        with page.expect_download() as event:page.get_by_role('button',name='Recovery receipt',exact=True).click()
        receipt=OUT/'continuation-receipt.json';event.value.save_as(str(receipt));proof=json.loads(receipt.read_text(encoding='utf-8'))
        assert proof['recovered']['pages']==8 and len(proof['continued_work']['created_records'])==3
        with page.expect_download() as event:page.get_by_role('button',name='Application',exact=True).click()
        fresh=OUT/'reexported.html';event.value.save_as(str(fresh))
        page.screenshot(path=str(OUT/'03-independent-continuation.png'),full_page=True)
        context.close();context=browser.new_context(accept_downloads=True);context.set_offline(True);page=context.new_page();page.goto(fresh.as_uri())
        page.get_by_role('button',name='Follow-ups',exact=True).click();expect(page.locator('.task-row')).to_have_count(2)
        # Explicit restore uses an actual matching backup, including local additions.
        page.locator('[data-process-restore]').set_input_files(str(backup));expect(page.locator('.runtime-notice')).to_contain_text('restored')
        page.evaluate('''key=>{const state=JSON.parse(localStorage.getItem(key));state.process.parent_revision='In progress';localStorage.setItem(key,JSON.stringify(state));}''','exitforge.workspace.v1.'+data['id'])
        page.reload();expect(page.locator('.runtime-notice')).to_contain_text('different rules')
        context.close();browser.close()
    assert not errors and not cloud and not offline_requests,(errors,cloud,offline_requests)
    result={'status':'passed','new_live_calls':0,'create_project_and_linked_items':True,'structured_edit_cannot_set_status':True,'local_provenance_and_original_model_preserved':True,'guarded_delivery_and_distinct_client_receipts':True,'offline_add_edit_reload_restore_reexport':True,'mobile_form_no_overflow':True,'page_errors':errors,'offline_http_requests':offline_requests}
    (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))


if __name__=='__main__':run()
