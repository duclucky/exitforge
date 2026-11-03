"""Regressions from the real Chrome review, plus a fresh offline artifact check."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parent.parent
EVIDENCE=Path(os.environ.get('EXITFORGE_TEST_EVIDENCE',ROOT.parent/'.hackathon/evidence/exitforge-chrome-review-2026-10-29')).resolve()
EVIDENCE.mkdir(parents=True,exist_ok=True)


def run():
    errors=[]
    with sync_playwright() as p:
        browser=p.chromium.launch()
        context=browser.new_context(viewport={'width':1133,'height':900},accept_downloads=True,reduced_motion='reduce')
        page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(os.environ.get('EXITFORGE_TEST_URL','http://127.0.0.1:8765'))
        # Empty/intercepted sample responses must not become a size error or a busy dead end.
        page.route('**/api/sample',lambda route:route.fulfill(status=204))
        page.get_by_role('button',name='Start guided demo').click()
        expect(page.locator('#studio-notice')).to_contain_text('unavailable')
        page.unroute('**/api/sample')
        page.get_by_role('button',name='Start guided demo').click()
        page.get_by_role('button',name='Review delivery rule',exact=True).click()
        expect(page.locator('#confirm-rule')).to_be_focused()
        expect(page.locator('#confirm-rule')).not_to_be_checked()
        page.locator('#confirm-rule').check()
        page.get_by_role('button',name='Confirm & open workspace').click()
        board_top=page.locator('.board-columns').bounding_box()['y']
        assert board_top<640, f'Actual board starts below the useful demo viewport: {board_top}'
        page.screenshot(path=str(EVIDENCE/'01-focused-workspace.png'))
        page.get_by_role('button',name='Open demo project').click()
        dialog=page.get_by_role('dialog',name='Project details')
        dialog.get_by_label('Project status').select_option('Delivered')
        expect(dialog.locator('.dialog-message')).to_contain_text('Complete the handoff checklist')
        expect(dialog.locator('.dialog-message')).to_have_class('dialog-message error')
        message_rect=dialog.locator('.dialog-message').bounding_box()
        assert 0<=message_rect['y']<800 and message_rect['y']+message_rect['height']<=900
        page.screenshot(path=str(EVIDENCE/'02-visible-guard.png'))
        dialog.get_by_role('checkbox',name='Get final approval').check()
        dialog.get_by_label('Project status').select_option('Delivered')
        expect(dialog.locator('.dialog-message')).to_contain_text('New follow-up')
        expect(dialog.locator('.dialog-message')).to_contain_text('Check in after delivery')
        page.screenshot(path=str(EVIDENCE/'03-delivery-receipt.png'))
        dialog.get_by_role('button',name='View follow-up',exact=True).click()
        expect(dialog).not_to_be_visible()
        expect(page.locator('.task-row')).to_have_count(1)
        expect(page.locator('[data-view="tasks"]')).to_be_focused()
        page.get_by_role('button',name='Open demo project').click()
        dialog.get_by_label('Project status').select_option('Review')
        dialog.get_by_label('Project status').select_option('Delivered')
        expect(dialog.locator('.dialog-message')).to_contain_text('Existing follow-up')
        dialog.get_by_role('button',name='View follow-up',exact=True).click()
        expect(page.locator('.task-row')).to_have_count(1)
        page.get_by_role('button',name='Take it with you').click()
        with page.expect_download() as event:page.get_by_role('button',name='Download independent app').click()
        artifact=EVIDENCE/'review-independent.html';event.value.save_as(str(artifact))
        assert artifact.stat().st_size>10000
        context.close()
        offline=browser.new_context(viewport={'width':390,'height':844},accept_downloads=True)
        offline.set_offline(True);page=offline.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(artifact.as_uri())
        page.get_by_label('Find a project or page').fill('Spring campaign')
        page.locator('.project-card').filter(has=page.locator('strong',has_text='Spring campaign')).filter(has_text='Cedar').click()
        dialog=page.get_by_role('dialog',name='Project details')
        dialog.get_by_role('checkbox',name='Get final approval').check()
        dialog.get_by_label('Project status').select_option('Delivered')
        dialog.get_by_role('button',name='View follow-up',exact=True).click()
        # Receipt navigation clears the previous project search so its task is visible.
        expect(page.get_by_label('Find a project or page')).to_have_value('')
        expect(page.locator('.task-row')).to_have_count(2)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.reload()
        page.get_by_role('button',name='Follow-ups',exact=False).click()
        expect(page.locator('.task-row')).to_have_count(2)
        page.screenshot(path=str(EVIDENCE/'04-offline-mobile-followups.png'),full_page=True)
        assert not errors,errors
        offline.close();browser.close()
    result={'status':'passed','sample_empty_response_recovery':True,'explicit_confirmation':True,
            'board_top_1133x900':board_top,'visible_guard_feedback':True,'real_followup_receipt':True,
            'idempotency':True,'offline_receipt_navigation_and_reload':True,'page_errors':errors}
    (EVIDENCE/'browser-review-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':run()
