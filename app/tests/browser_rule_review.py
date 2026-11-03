"""Recorded real proposal, explicit correction and offline reuse; zero inference."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parent.parent
EVIDENCE=Path(os.environ.get('EXITFORGE_TEST_EVIDENCE',ROOT.parent/'.hackathon/evidence/exitforge-upgrade-2026-11-02/rule-review')).resolve()
FIXTURE=ROOT/'examples/meta-handoff-original.json'


def run():
    EVIDENCE.mkdir(parents=True,exist_ok=True)
    errors=[];calls=[];external=[]
    with sync_playwright() as p:
        browser=p.chromium.launch()
        context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
        page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('request',lambda request:calls.append(request.url) if request.url.endswith(('/api/enhance','/api/modal-package')) else None)
        page.goto(os.environ.get('EXITFORGE_TEST_URL','http://127.0.0.1:8765'))
        page.get_by_role('button',name='Explore Meta-assisted example').click()
        expect(page.get_by_role('region',name='Meta contribution')).to_contain_text('RECORDED REAL META RUN')
        expect(page.get_by_role('region',name='Meta contribution')).to_contain_text('Parser workflow: not selected')
        expect(page.locator('#status-field')).to_have_value('Release phase')
        expect(page.locator('#checklist-warning')).to_contain_text('2 projects have unfinished checklists')
        page.locator('#require-checklist').check()
        expect(page.locator('#checklist-warning')).not_to_be_visible()
        expect(page.locator('#confirm-rule')).not_to_be_checked()
        expect(page.locator('#studio-notice')).to_contain_text('no new API call')
        page.get_by_role('button',name='Import workspace',exact=True).click()
        page.locator('#workspace-file').set_input_files(str(FIXTURE))
        expect(page.get_by_role('region',name='Meta contribution')).to_contain_text('Meta proposed. You decide.')
        expect(page.locator('#followup-preview')).to_contain_text('Make this AI follow-up reusable')
        page.locator('#confirm-rule').check()
        page.get_by_role('button',name='Confirm & open workspace').click()
        expect(page.locator('#studio-notice')).to_contain_text('include {project} and {client}')
        expect(page.locator('#followup-text')).to_be_focused()
        page.get_by_role('button',name='Use reusable task template').click()
        expect(page.locator('#confirm-rule')).not_to_be_checked()
        examples=page.locator('.followup-examples li')
        expect(examples).to_have_count(3)
        expect(examples.filter(has_text='Website refresh')).to_contain_text('Confirm Cedar & Co received Website refresh.')
        expect(examples.filter(has_text='Packaging system')).to_contain_text('Confirm Lumen Collective received Packaging system.')
        page.get_by_role('button',name='Inspect Meta reasoning').click()
        expect(page.get_by_role('region',name='AI proposal')).to_be_focused()
        page.locator('#followup-text').focus()
        page.screenshot(path=str(EVIDENCE/'01-review-desktop.png'),full_page=True)
        # The correction persists independently from the unmodified recorded response.
        page.reload();page.get_by_role('button',name='Resume saved workspace').click()
        expect(page.locator('#followup-text')).to_have_value('Confirm {client} received {project}.')
        with page.expect_download() as event:page.get_by_role('button',name='Download recovery receipt').click()
        event.value.save_as(str(EVIDENCE/'review-receipt.json'))
        receipt=json.loads((EVIDENCE/'review-receipt.json').read_text())
        assert 'Northstar' in receipt['meta_proposal']['specification']['followup']
        assert receipt['unconfirmed_review']['followup']=='Confirm {client} received {project}.'
        assert receipt['workflow']['confirmed'] is False
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.locator('#followup-preview').screenshot(path=str(EVIDENCE/'02-client-previews-mobile.png'))
        page.locator('#confirm-rule').check();page.get_by_role('button',name='Confirm & open workspace').click()
        page.locator('.project-card').filter(has_text='Website refresh').click()
        dialog=page.get_by_role('dialog',name='Project details')
        for checkbox in dialog.get_by_role('checkbox').all():checkbox.check()
        dialog.get_by_label('Project status').select_option('Delivered')
        expect(dialog.locator('.dialog-message')).to_contain_text('Confirm Cedar & Co received Website refresh.')
        dialog.get_by_role('button',name='Close project details').click()
        page.get_by_role('button',name='Take it with you').click()
        with page.expect_download() as event:page.get_by_role('button',name='Recovery receipt',exact=True).click()
        event.value.save_as(str(EVIDENCE/'approved-receipt.json'))
        with page.expect_download() as event:page.get_by_role('button',name='Download independent app').click()
        artifact=EVIDENCE/'corrected-independent.html';event.value.save_as(str(artifact))
        context.close()
        offline=browser.new_context(viewport={'width':390,'height':844},accept_downloads=True)
        offline.set_offline(True);page=offline.new_page()
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('request',lambda request:external.append(request.url) if request.url.startswith(('https:','http:')) else None)
        page.goto(artifact.as_uri())
        page.get_by_role('button',name='Follow-ups',exact=False).click()
        expect(page.locator('.task-row')).to_contain_text('Confirm Cedar & Co received Website refresh.')
        page.locator('.task-row input').check();page.reload()
        page.get_by_role('button',name='Follow-ups',exact=False).click()
        expect(page.locator('.task-row input')).to_be_checked()
        assert not errors and not calls and not external,(errors,calls,external)
        browser.close()
    result={'status':'passed','raw_proposal_preserved':True,'incorrect_global_ai_rule_blocked':True,
      'three_client_preview':True,'explicit_contextual_correction':True,'draft_reload':True,
      'receipt_distinguishes_proposal_from_approval':True,'correct_client_task_offline':True,
      'new_live_calls':0,'errors':errors}
    (EVIDENCE/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':run()
