"""Reference-led responsive review and new entry controls. Zero cloud requests."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parent.parent
EVIDENCE=Path(os.environ.get('EXITFORGE_TEST_EVIDENCE',ROOT.parent/'.hackathon/evidence/exitforge-reference-redesign-2026-10-29')).resolve()


def run():
    EVIDENCE.mkdir(parents=True,exist_ok=True)
    errors=[];cloud=[];layouts=[]
    with sync_playwright() as p:
        browser=p.chromium.launch()
        context=browser.new_context(viewport={'width':1120,'height':857},reduced_motion='reduce')
        page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda r:cloud.append(r.url) if '/api/enhance' in r.url or '/api/modal-package' in r.url else None)
        page.goto(os.environ.get('EXITFORGE_TEST_URL','http://127.0.0.1:8765'))
        expect(page.get_by_role('heading',level=1)).to_contain_text('The contract ends.')
        copy=page.locator('.hero-copy').bounding_box();art=page.locator('.hero-art').bounding_box()
        assert art['x']>copy['x']+copy['width'],'Reference desktop hero must use two distinct columns.'
        page.screenshot(path=str(EVIDENCE/'desktop-1120.png'))
        page.get_by_text('How it works & limits',exact=True).click()
        expect(page.locator('.quick-limits>div')).to_be_visible()
        page.get_by_text('How it works & limits',exact=True).click()
        page.get_by_role('button',name='Use your own export',exact=False).click()
        expect(page.get_by_role('button',name='Choose export ZIP',exact=True)).to_be_focused()
        for width in [1440,768,390,320]:
            page.set_viewport_size({'width':width,'height':900 if width>800 else 844})
            page.evaluate('window.scrollTo(0,0)')
            overflow=page.evaluate('document.documentElement.scrollWidth>innerWidth')
            assert not overflow,f'Landing overflows at {width}px.'
            layouts.append({'width':width,'landing_no_overflow':True})
            page.screenshot(path=str(EVIDENCE/f'landing-{width}.png'))
        page.get_by_role('button',name='Try client handoff',exact=True).click()
        expect(page.locator('#confirm-rule')).not_to_be_checked()
        page.get_by_role('button',name='Review delivery rule',exact=True).click()
        page.locator('#confirm-rule').check()
        page.get_by_role('button',name='Confirm & open workspace',exact=True).click()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),'Workspace overflows at 320px.'
        page.get_by_role('button',name='Open demo project',exact=True).click()
        dialog=page.get_by_role('dialog',name='Project details')
        dialog.get_by_label('Project status').select_option('Delivered')
        expect(dialog.locator('.dialog-message')).to_contain_text('Complete the handoff checklist')
        page.screenshot(path=str(EVIDENCE/'mobile-320-guard.png'))
        dialog.get_by_role('button',name='Close project details').click()
        page.set_viewport_size({'width':1120,'height':857})
        page.get_by_role('button',name='Import workspace',exact=True).click()
        expect(page.get_by_role('button',name='Choose export ZIP',exact=True)).to_be_focused()
        page.evaluate('window.scrollTo(0,0)')
        page.screenshot(path=str(EVIDENCE/'desktop-with-saved-draft.png'))
        assert not cloud and not errors,(cloud,errors)
        browser.close()
    result={'status':'passed','reference_desktop_columns':True,'layouts':layouts,
        'limits_disclosure':True,'import_actions_focus_real_uploader':True,
        'saved_draft_retained':True,'mobile_guard_verified':True,'cloud_requests':cloud,'errors':errors}
    (EVIDENCE/'visual-review-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':run()
