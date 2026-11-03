"""Guided demo observations must come from real actions, not a scripted success state."""
import json
import os
import re
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = Path(os.environ.get('EXITFORGE_TEST_EVIDENCE', ROOT.parent / '.hackathon/evidence/exitforge-demo-polish-2026-10-29')).resolve()
EVIDENCE.mkdir(parents=True, exist_ok=True)


def run():
    errors, cloud, external = [], [], []
    with sync_playwright() as driver:
        browser = driver.chromium.launch()
        context = browser.new_context(viewport={'width': 1440, 'height': 1050}, accept_downloads=True, reduced_motion='reduce')
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: cloud.append(request.url) if '/api/enhance' in request.url or '/api/modal-package' in request.url else None)
        page.goto(os.environ.get('EXITFORGE_TEST_URL','http://127.0.0.1:8765'), wait_until='networkidle')
        page.screenshot(path=str(EVIDENCE / '01-import-desktop.png'), full_page=True)
        page.get_by_role('button', name='Start guided demo').click()
        expect(page.get_by_role('region', name='Guided demo')).to_contain_text('Confirm a rule')
        expect(page.locator('#confirm-rule')).not_to_be_checked()
        expect(page.locator('#cloud-consent')).not_to_be_checked()
        page.get_by_text('Inspect recovered source', exact=True).click()
        expect(page.locator('.source-preview')).to_contain_text('Brand launch')
        expect(page.locator('.source-preview')).to_contain_text('Get final approval')
        page.screenshot(path=str(EVIDENCE / '02-review-desktop.png'), full_page=True)
        page.locator('#confirm-rule').check()
        page.get_by_role('button', name='Confirm & open workspace').click()
        guide = page.get_by_role('region', name='Guided demo')
        expect(guide.locator('[data-proof="guard"]')).to_have_attribute('data-complete', 'false')
        expect(guide.locator('[data-proof="delivery"]')).to_have_attribute('data-complete', 'false')
        page.get_by_role('button', name='Open demo project').click()
        dialog = page.get_by_role('dialog', name='Project details')
        dialog.get_by_label('Project status').select_option('Delivered')
        expect(dialog.locator('.dialog-message')).to_contain_text('Complete the handoff checklist')
        expect(guide.locator('[data-proof="guard"]')).to_have_attribute('data-complete', 'true')
        dialog.get_by_role('checkbox', name='Get final approval').check()
        dialog.get_by_label('Project status').select_option('Delivered')
        page.keyboard.press('Escape')
        expect(page.get_by_role('button', name='Open demo project')).to_be_focused()
        expect(guide.locator('[data-proof="delivery"]')).to_have_attribute('data-complete', 'true')
        page.get_by_role('button', name='Follow-ups', exact=False).click()
        expect(page.locator('.task-row')).to_have_count(1)
        page.screenshot(path=str(EVIDENCE / '03-workspace-desktop.png'), full_page=True)
        # Undoing delivery invalidates the current-state observation.
        page.get_by_role('button', name='Open demo project').click()
        dialog.get_by_label('Project status').select_option('Review')
        dialog.get_by_role('button', name='Close project details').click()
        expect(guide.locator('[data-proof="delivery"]')).to_have_attribute('data-complete', 'false')
        page.get_by_role('button', name='Open demo project').click()
        dialog.get_by_label('Project status').select_option('Delivered')
        dialog.get_by_role('button', name='Close project details').click()
        expect(page.locator('.task-row')).to_have_count(1)
        page.get_by_role('button', name='Take it with you').click()
        expect(page.locator('#package-receipt')).to_have_count(0)
        page.route('**/api/package', lambda route: route.fulfill(status=500, content_type='application/json', body='{"error":"Test-only packaging failure"}'))
        page.get_by_role('button', name='Download independent app').click()
        expect(page.locator('#studio-notice')).to_contain_text('Test-only packaging failure')
        expect(page.locator('#package-receipt')).to_have_count(0)
        page.unroute('**/api/package')
        with page.expect_download() as event:
            page.get_by_role('button', name='Download independent app').click()
        portable = EVIDENCE / 'northstar-demo.html'
        event.value.save_as(str(portable))
        receipt = page.get_by_role('status', name='Application download')
        expect(receipt).to_contain_text('Northstar-workspace.html')
        expect(receipt).to_contain_text('Open the file')
        expect(receipt).not_to_contain_text('Offline verified')
        page.evaluate('scrollTo(0,0)')
        page.screenshot(path=str(EVIDENCE / '04-export-desktop.png'), full_page=True)
        # Re-entering a view must not show an obsolete package receipt.
        page.get_by_role('button', name='Back to workspace').click()
        page.get_by_role('button', name='Take it with you').click()
        expect(page.locator('#package-receipt')).to_have_count(0)
        page.set_viewport_size({'width': 390, 'height': 844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path=str(EVIDENCE / '05-export-mobile.png'), full_page=True)
        page.get_by_role('button', name='Back to workspace').click()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert page.get_by_role('button', name='Take it with you').bounding_box()['width'] > 130
        page.screenshot(path=str(EVIDENCE / '06-workspace-mobile.png'), full_page=True)
        page.get_by_role('button', name='Exit guided demo').click()
        expect(page.get_by_role('region', name='Guided demo')).to_have_count(0)
        # Keyboard-accessible source inspection and normal sample path stay usable.
        page.locator('[data-step="0"]').click()
        page.get_by_role('button', name='Try sample workspace').click()
        expect(page.get_by_role('region', name='Guided demo')).to_have_count(0)
        page.locator('.source-inspector summary').focus()
        page.keyboard.press('Enter')
        expect(page.locator('.source-preview')).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path=str(EVIDENCE / '07-review-mobile.png'), full_page=True)
        context.close()

        offline = browser.new_context(viewport={'width': 1440, 'height': 1000}, accept_downloads=True)
        offline.set_offline(True)
        page = offline.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: external.append(request.url) if request.url.startswith(('http:', 'https:')) else None)
        page.goto(portable.as_uri())
        expect(page.locator('.project-card')).to_have_count(30)
        page.locator('.project-card').filter(has=page.locator('strong', has_text=re.compile(r'^Brand launch$'))).click()
        dialog = page.get_by_role('dialog', name='Project details')
        expect(dialog.get_by_label('Project status')).to_have_value('Delivered')
        dialog.locator('summary').click()
        dialog.get_by_label('Notes (Markdown)').fill('# Brand launch\n\nThe original service is gone. The work continues.')
        dialog.get_by_role('button', name='Save notes').click()
        dialog.get_by_role('button', name='Close project details').click()
        page.reload()
        page.locator('.project-card').filter(has=page.locator('strong', has_text=re.compile(r'^Brand launch$'))).click()
        expect(page.locator('.page-body')).to_contain_text('The work continues.')
        page.get_by_role('button', name='Close project details').click()
        page.get_by_role('button', name='Follow-ups', exact=False).click()
        expect(page.locator('.task-row')).to_have_count(1)
        page.screenshot(path=str(EVIDENCE / '08-independent-offline.png'), full_page=True)
        assert not cloud, cloud
        assert not external, external
        assert not errors, errors
        offline.close()
        browser.close()
    result = {'guided_actions': 'passed', 'mobile_and_keyboard': 'passed', 'offline_edit_reload': 'passed',
              'cloud_calls': len(cloud), 'offline_http_requests': len(external), 'page_errors': errors,
              'portable_bytes': portable.stat().st_size}
    (EVIDENCE / 'browser-demo-result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    run()
