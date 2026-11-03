"""Real Chromium journey, including the downloaded file with networking disabled."""

import json
import os
import re
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parent.parent
EVIDENCE=Path(os.environ.get('EXITFORGE_TEST_EVIDENCE',ROOT.parent/'.hackathon/evidence/exitforge-local-mvp')).resolve()
EVIDENCE.mkdir(parents=True,exist_ok=True)


def run():
    errors=[]
    with sync_playwright() as driver:
        browser=driver.chromium.launch(headless=True)
        context=browser.new_context(viewport={'width':1440,'height':1050},accept_downloads=True)
        page=context.new_page()
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(os.environ.get('EXITFORGE_TEST_URL','http://127.0.0.1:8765'),wait_until='networkidle')
        page.screenshot(path=str(EVIDENCE/'01-import.png'),full_page=True)
        page.get_by_role('button',name='Try sample workspace').click()
        expect(page.get_by_role('heading',name='Declare your delivery workflow')).to_be_visible()
        expect(page.locator('#delivery-state')).to_have_value('Delivered')
        page.locator('#confirm-rule').check()
        page.get_by_role('button',name='Confirm & open workspace').click()
        expect(page.locator('.project-card')).to_have_count(30)
        page.screenshot(path=str(EVIDENCE/'02-workspace.png'),full_page=True)
        page.locator('.project-card').filter(has=page.locator('strong',has_text=re.compile(r'^Brand launch$'))).click()
        dialog=page.get_by_role('dialog',name='Project details')
        dialog.get_by_label('Project status').select_option('Delivered')
        expect(dialog.locator('.dialog-message')).to_contain_text('Complete the handoff checklist')
        expect(dialog.get_by_label('Project status')).to_have_value('In progress')
        dialog.get_by_role('checkbox',name='Get final approval').check()
        dialog.get_by_label('Project status').select_option('Delivered')
        expect(dialog.locator('.dialog-message')).to_contain_text('Stage updated')
        dialog.get_by_role('button',name='Close project details').click()
        page.get_by_role('button',name='Follow-ups',exact=False).click()
        expect(page.locator('.task-row')).to_have_count(1)
        page.get_by_role('button',name='Take it with you').click()
        with page.expect_download() as event:
            page.get_by_role('button',name='Download independent app').click()
        portable=EVIDENCE/'northstar-independent.html'
        event.value.save_as(str(portable))
        context.close()

        offline=browser.new_context(viewport={'width':1440,'height':1050},accept_downloads=True)
        offline.set_offline(True)
        filepage=offline.new_page()
        filepage.on('pageerror',lambda error:errors.append(str(error)))
        requests=[]
        filepage.on('request',lambda request:requests.append(request.url) if request.url.startswith(('http:','https:')) else None)
        filepage.goto(portable.as_uri(),wait_until='load')
        expect(filepage.locator('.project-card')).to_have_count(30)
        filepage.locator('.project-card').filter(has=filepage.locator('strong',has_text=re.compile(r'^Spring campaign$'))).click()
        dialog=filepage.get_by_role('dialog',name='Project details')
        dialog.get_by_role('checkbox',name='Get final approval').check()
        dialog.get_by_label('Project status').select_option('Delivered')
        dialog.locator('summary').click()
        dialog.get_by_label('Notes (Markdown)').fill('# Spring campaign\n\nAn actual edit made with networking disabled.\n\nOffline persistence proof.')
        dialog.get_by_role('button',name='Save notes').click()
        expect(dialog.locator('.page-body')).to_contain_text('Offline persistence proof.')
        with filepage.expect_download() as event:
            dialog.locator('[data-asset]').click()
        event.value.save_as(str(EVIDENCE/'delivery-notes.txt'))
        assert 'working files' in (EVIDENCE/'delivery-notes.txt').read_text()
        dialog.get_by_role('button',name='Close project details').click()
        filepage.reload(wait_until='load')
        filepage.locator('.project-card').filter(has=filepage.locator('strong',has_text=re.compile(r'^Spring campaign$'))).click()
        dialog=filepage.get_by_role('dialog',name='Project details')
        expect(dialog.locator('.page-body')).to_contain_text('Offline persistence proof.')
        expect(dialog.get_by_label('Project status')).to_have_value('Delivered')
        dialog.get_by_role('button',name='Close project details').click()
        filepage.get_by_role('button',name='Follow-ups',exact=False).click()
        expect(filepage.locator('.task-row')).to_have_count(2)
        filepage.screenshot(path=str(EVIDENCE/'03-offline-followups.png'),full_page=True)
        with filepage.expect_download() as event:
            filepage.get_by_role('button',name='Data backup',exact=True).click()
        backup=EVIDENCE/'offline-current-data.json';event.value.save_as(str(backup))
        restored=json.loads(backup.read_text(encoding='utf-8'))
        spring=next(p for p in restored['pages'] if p['title']=='Spring campaign')
        assert 'Offline persistence proof.' in spring['body']
        assert len(restored['tasks'])==2
        with filepage.expect_download() as event:
            filepage.get_by_role('button',name='Application',exact=True).click()
        latest=EVIDENCE/'northstar-updated.html';event.value.save_as(str(latest))
        # A fresh browser context proves the second export embeds current state.
        fresh=browser.new_context(viewport={'width':390,'height':844})
        fresh.set_offline(True)
        mobile=fresh.new_page();mobile.on('pageerror',lambda error:errors.append(str(error)))
        mobile.goto(latest.as_uri(),wait_until='load')
        mobile.get_by_role('button',name='Follow-ups',exact=False).click()
        expect(mobile.locator('.task-row')).to_have_count(2)
        assert mobile.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        mobile.screenshot(path=str(EVIDENCE/'04-mobile-offline.png'),full_page=True)
        assert not requests,requests
        assert not errors,errors
        browser.close()
    result={'status':'passed','checks':['sample import: 30 projects','explicit workflow confirmation','incomplete checklist blocks delivery','exactly one follow-up per delivered project','standalone HTML download','offline editing','offline attachment download','reload preserves actual edits','fresh data backup contains current state','application re-export embeds current state in a fresh offline browser','390px layout has no horizontal overflow','zero HTTP(S) requests from offline application','zero browser page errors'],
            'limitations':['Purpose-created Notion-style sample, not a real customer workspace','No live Meta, Baseten, Fireworks or Modal calls','Chromium only; file-origin storage differs by browser']}
    (EVIDENCE/'browser-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':run()
