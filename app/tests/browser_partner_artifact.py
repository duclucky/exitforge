"""Verify the existing real partner artifact offline. This makes no cloud call."""
import json
from pathlib import Path
import re
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parent.parent
EVIDENCE=ROOT.parent/'.hackathon/evidence/exitforge-impact-api-2026-10-29'


def run():
    artifact=EVIDENCE/'modal-handoff-independent.html'
    errors,external=[],[]
    with sync_playwright() as p:
        browser=p.chromium.launch()
        context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
        context.set_offline(True)
        page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda r:external.append(r.url) if r.url.startswith(('http:','https:')) else None)
        page.goto(artifact.as_uri())
        expect(page.locator('.project-card')).to_have_count(3)
        expect(page.locator('.workspace-header')).to_contain_text("Avery's handoff desk")
        page.locator('.project-card').filter(has=page.locator('strong',has_text=re.compile('^Brand launch$'))).click()
        dialog=page.get_by_role('dialog',name='Project details')
        dialog.get_by_label('Project status').select_option('Delivered')
        expect(dialog.locator('.dialog-message')).to_contain_text('Complete the handoff checklist')
        dialog.get_by_role('checkbox',name='Get final approval').check()
        dialog.get_by_label('Project status').select_option('Delivered')
        expect(dialog.locator('.dialog-message')).to_contain_text('Confirm Northstar received')
        dialog.get_by_role('button',name='View follow-up',exact=True).click()
        expect(page.locator('.task-row')).to_have_count(1)
        page.screenshot(path=str(EVIDENCE/'partner-artifact-offline.png'))
        page.reload()
        page.get_by_role('button',name='Follow-ups',exact=False).click()
        expect(page.locator('.task-row')).to_have_count(1)
        with page.expect_download() as event:page.get_by_role('button',name='Data backup',exact=True).click()
        backup=EVIDENCE/'partner-current-backup.json';event.value.save_as(str(backup))
        workspace=json.loads(backup.read_text(encoding='utf-8'))
        assert len(workspace['pages'])==7 and len(workspace['assets'])==3 and len(workspace['tasks'])==1
        assert workspace['presentation']['primary_view']=='board'
        assert workspace['provenance']['cloud_calls'][0]['provider']=='Baseten'
        assert workspace['provenance']['cloud_calls'][0]['event_model'] is False
        assert not external and not errors,(external,errors)
        context.close();browser.close()
    result={'status':'passed','artifact':'Actual private Modal compiler output using actual Baseten public-model presentation',
            'offline_delivery_guard':True,'receipt_task_persists_after_reload':True,'backup_verified':True,
            'http_requests':external,'errors':errors,'new_cloud_calls':0,'full_four_provider_flow':False}
    (EVIDENCE/'partner-artifact-browser-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))


if __name__=='__main__':run()
