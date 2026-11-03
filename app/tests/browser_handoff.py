"""Executable impact illustration; technical continuity evidence, not a user study."""
import json
import os
from pathlib import Path
import re
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parent.parent
EVIDENCE=Path(os.environ.get('EXITFORGE_TEST_EVIDENCE',ROOT.parent/'.hackathon/evidence/exitforge-impact-api-2026-10-29/handoff')).resolve()
EVIDENCE.mkdir(parents=True,exist_ok=True)


def run():
    errors,cloud,external=[],[],[]
    with sync_playwright() as p:
        browser=p.chromium.launch()
        context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
        page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda r:cloud.append(r.url) if '/api/enhance' in r.url or '/api/modal-package' in r.url else None)
        page.goto(os.environ.get('EXITFORGE_TEST_URL','http://127.0.0.1:8765'))
        expect(page.get_by_role('heading',name=re.compile(r'The contract ends\.\s*Your work continues\.'))).to_have_count(1)
        page.screenshot(path=str(EVIDENCE/'01-impact-entry.png'),full_page=True)
        page.get_by_role('button',name='Try client handoff',exact=True).click()
        expect(page.get_by_role('region',name='Client handoff scenario')).to_contain_text('Fictional scenario')
        expect(page.locator('#followup-text')).to_have_value('Confirm {client} received {project}.')
        expect(page.locator('#followup-preview')).to_contain_text('Confirm Northstar Studio received Brand launch.')
        expect(page.locator('#confirm-rule')).not_to_be_checked()
        page.get_by_text('Inspect recovered source',exact=True).click()
        expect(page.locator('.source-preview')).to_contain_text('logo pack')
        page.get_by_role('button',name='Review delivery rule',exact=True).click()
        page.locator('#confirm-rule').check()
        page.get_by_role('button',name='Confirm & open workspace').click()
        expect(page.locator('.project-card')).to_have_count(3)
        page.get_by_role('button',name='Open demo project').click()
        dialog=page.get_by_role('dialog',name='Project details')
        dialog.get_by_label('Project status').select_option('Delivered')
        expect(dialog.locator('.dialog-message')).to_contain_text('Complete the handoff checklist')
        dialog.locator('.page-body').get_by_role('button',name='Client context',exact=True).click()
        expect(dialog.get_by_role('heading',name='Northstar Studio',exact=True)).to_be_visible()
        expect(dialog.locator('.page-body')).to_contain_text('Final approval is still pending')
        dialog.get_by_role('button',name='Close project details').click()
        page.get_by_role('button',name='Open demo project').click()
        dialog.get_by_role('checkbox',name='Get final approval').check()
        dialog.get_by_label('Project status').select_option('Delivered')
        expect(dialog.locator('.dialog-message')).to_contain_text('Confirm Northstar Studio received Brand launch.')
        page.screenshot(path=str(EVIDENCE/'02-concrete-handoff.png'))
        dialog.get_by_role('button',name='View follow-up',exact=True).click()
        expect(page.locator('.task-row')).to_have_count(1)
        expect(page.locator('.task-row')).to_contain_text('Confirm Northstar Studio received Brand launch.')
        page.get_by_role('button',name='Take it with you').click()
        with page.expect_download() as event:page.get_by_role('button',name='Download independent app').click()
        artifact=EVIDENCE/'avery-handoff-independent.html';event.value.save_as(str(artifact))
        context.close()
        offline=browser.new_context(viewport={'width':390,'height':844},accept_downloads=True)
        offline.set_offline(True);page=offline.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda r:external.append(r.url) if r.url.startswith(('http:','https:')) else None)
        page.goto(artifact.as_uri())
        expect(page.locator('.project-card')).to_have_count(3)
        page.locator('.project-card').filter(has=page.locator('strong',has_text=re.compile('^Brand launch$'))).click()
        dialog=page.get_by_role('dialog',name='Project details')
        expect(dialog.get_by_label('Project status')).to_have_value('Delivered')
        with page.expect_download() as event:dialog.locator('[data-asset]').click()
        notes=EVIDENCE/'northstar-handoff-notes.txt';event.value.save_as(str(notes))
        assert 'logo pack' in notes.read_text(encoding='utf-8')
        dialog.locator('.edit-notes summary').click()
        dialog.get_by_label('Notes (Markdown)').fill('# Brand launch\n\nClient receipt confirmed after the original workspace access ended.')
        dialog.get_by_role('button',name='Save notes',exact=True).click()
        dialog.get_by_role('button',name='Close project details').click();page.reload()
        page.locator('.project-card').filter(has=page.locator('strong',has_text=re.compile('^Brand launch$'))).click()
        expect(page.locator('.page-body')).to_contain_text('Client receipt confirmed')
        page.get_by_role('button',name='Close project details').click()
        page.get_by_role('button',name='Follow-ups',exact=False).click()
        expect(page.locator('.task-row')).to_have_count(1)
        with page.expect_download() as event:page.get_by_role('button',name='Data backup',exact=True).click()
        backup=EVIDENCE/'avery-current-backup.json';event.value.save_as(str(backup))
        data=json.loads(backup.read_text(encoding='utf-8'));assert len(data['pages'])==7 and len(data['assets'])==3 and len(data['tasks'])==1
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(EVIDENCE/'03-offline-continuity.png'),full_page=True)
        assert not errors and not cloud and not external,(errors,cloud,external)
        offline.close();browser.close()
    result={'status':'passed','scenario':'Fictional independent designer with an authorized export',
            'source_pages':7,'handoffs':3,'included_txt_assets':3,'northstar_followups':1,
            'offline_edit_reload_backup':True,'cloud_calls':0,'offline_http_requests':0,
            'human_impact_validated':False,'measured_time_saving':None,'errors':errors}
    (EVIDENCE/'handoff-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))


if __name__=='__main__':run()
