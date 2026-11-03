"""Local search and contextual follow-up regressions, including the offline runtime."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parent.parent
EVIDENCE=Path(os.environ.get('EXITFORGE_TEST_EVIDENCE',ROOT.parent/'.hackathon/evidence/exitforge-product-polish-2026-10-29')).resolve()
BASE=os.environ.get('EXITFORGE_TEST_URL','http://127.0.0.1:8765')


def exercise_search(page):
    search=page.get_by_role('searchbox',name='Find a project or page')
    for view,selector in [('Projects','.project-card'),('Documents','.document-card'),
                          ('Follow-ups','.task-row'),('Activity','.activity-row')]:
        page.get_by_role('button',name=view,exact=False).click()
        search.fill('no-result-for-this-query')
        expect(page.locator(selector)).to_have_count(0)
        expect(page.get_by_role('button',name='Clear search',exact=True)).to_be_visible()
        expect(page.locator('.workspace-content')).to_contain_text('No matches')
        if view=='Documents':page.locator('[data-reset-search]').click()
        else:page.get_by_role('button',name='Clear search',exact=True).click()
        expect(search).to_have_value('')
        expect(search).to_be_focused()
        assert page.locator(selector).count()>0
    page.get_by_role('button',name='Follow-ups',exact=False).click()
    search.fill('  CEDAR  ')
    expect(page.locator('.task-row')).to_have_count(1)
    expect(page.locator('.task-row')).to_contain_text('Cedar & Co')
    expect(page.locator('.task-row')).not_to_contain_text('Northstar')
    page.get_by_role('button',name='Documents',exact=True).click()
    expect(search).to_have_value('  CEDAR  ')
    expect(page.locator('.document-card').filter(has_text='Website refresh')).to_have_count(1)
    page.get_by_role('button',name='Clear search',exact=True).click()


def run():
    EVIDENCE.mkdir(parents=True,exist_ok=True)
    errors=[];cloud=[];external=[]
    with sync_playwright() as p:
        browser=p.chromium.launch()
        context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
        page=context.new_page()
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('request',lambda r:cloud.append(r.url) if '/api/enhance' in r.url or '/api/modal-package' in r.url else None)
        page.goto(BASE)
        page.get_by_role('button',name='Try client handoff',exact=True).click()
        # Confirm a real missing behavior on the baseline before changing production.
        page.locator('#followup-text').fill('Confirm {client} received {project}.')
        page.locator('#confirm-rule').check()
        page.get_by_role('button',name='Confirm & open workspace',exact=True).click()
        for title in ['Brand launch','Website refresh']:
            page.locator('.project-card').filter(has=page.locator('strong',has_text=title)).click()
            dialog=page.get_by_role('dialog',name='Project details')
            for item in dialog.locator('[data-check]').all():item.check()
            dialog.get_by_label('Project status').select_option('Delivered')
            dialog.get_by_role('button',name='Close project details').click()
        exercise_search(page)
        page.screenshot(path=str(EVIDENCE/'01-studio-search.png'),full_page=True)
        page.locator('.step-nav [data-step="1"]').click()
        expect(page.locator('#followup-preview')).to_contain_text('Confirm Northstar Studio received Brand launch.')
        page.locator('#followup-text').fill('Receipt for {project} / {client}')
        expect(page.locator('#followup-preview')).to_contain_text('Receipt for Brand launch / Northstar Studio')
        page.set_viewport_size({'width':320,'height':844})
        page.locator('#followup-preview').scroll_into_view_if_needed()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(EVIDENCE/'03-rule-preview-mobile.png'))
        page.set_viewport_size({'width':1440,'height':1000})
        page.reload()
        page.get_by_role('button',name='Resume saved workspace',exact=False).click()
        expect(page.locator('#followup-text')).to_have_value('Receipt for {project} / {client}')
        expect(page.locator('#confirm-rule')).not_to_be_checked()
        page.locator('#confirm-rule').check()
        page.get_by_role('button',name='Confirm & open workspace',exact=True).click()
        page.get_by_role('button',name='Take it with you',exact=False).click()
        with page.expect_download() as event:
            page.get_by_role('button',name='Download independent app',exact=False).click()
        artifact=EVIDENCE/'contextual-handoff.html';event.value.save_as(str(artifact))
        context.close()
        offline=browser.new_context(viewport={'width':390,'height':844},accept_downloads=True)
        offline.set_offline(True);page=offline.new_page()
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('request',lambda r:external.append(r.url) if r.url.startswith(('http:','https:')) else None)
        page.goto(artifact.as_uri())
        exercise_search(page)
        page.get_by_role('button',name='Follow-ups',exact=False).click()
        expect(page.locator('.task-row')).to_have_count(2)
        expect(page.locator('.task-row').filter(has_text='Northstar Studio')).to_contain_text('Brand launch')
        expect(page.locator('.task-row').filter(has_text='Cedar & Co')).to_contain_text('Website refresh')
        page.locator('[data-task]').first.check()
        expect(page.locator('.workspace-overview > div').nth(2).locator('strong')).to_have_text('1')
        page.reload()
        page.get_by_role('button',name='Follow-ups',exact=False).click()
        expect(page.locator('[data-task]').first).to_be_checked()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(EVIDENCE/'02-offline-mobile-followups.png'),full_page=True)
        with page.expect_download() as event:page.get_by_role('button',name='Data backup',exact=True).click()
        backup=EVIDENCE/'contextual-backup.json';event.value.save_as(str(backup))
        saved=json.loads(backup.read_text(encoding='utf-8'))
        assert len(saved['tasks'])==2 and saved['workflow']['followup']=='Receipt for {project} / {client}'
        offline.close();browser.close()
    assert not errors and not cloud and not external,(errors,cloud,external)
    result={'status':'passed','multi_client_tasks':2,'search_all_four_views':True,
            'clear_restores_focus':True,'trim_case_context_search':True,'draft_preview_reload':True,
            'offline_search_edit_reload_backup':True,'cloud_calls':cloud,'offline_http':external,'errors':errors}
    (EVIDENCE/'product-polish-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':run()
