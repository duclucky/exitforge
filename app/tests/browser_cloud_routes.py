"""Route consent and recorded-proposal replay; zero provider calls."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parent.parent
FIXTURES=ROOT/'examples'
EVIDENCE=Path(os.environ.get('EXITFORGE_TEST_EVIDENCE',ROOT.parent/'.hackathon/evidence/exitforge-upgrade-2026-11-02/cloud-routes')).resolve()


def run():
    EVIDENCE.mkdir(parents=True,exist_ok=True)
    calls=[];errors=[]
    with sync_playwright() as p:
        browser=p.chromium.launch()
        context=browser.new_context(viewport={'width':390,'height':844},accept_downloads=True)
        page=context.new_page()
        page.on('request',lambda r:calls.append(r.url) if r.url.endswith('/api/enhance') else None)
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(os.environ.get('EXITFORGE_TEST_URL','http://127.0.0.1:8765'))
        page.get_by_role('button',name='Try client handoff',exact=True).click()
        page.locator('.cloud-options > summary').click()
        page.locator('#cloud-consent').check()
        page.get_by_label('AI route',exact=True).select_option('direct')
        expect(page.locator('#cloud-consent')).not_to_be_checked()
        expect(page.locator('#ai-consent-description')).to_contain_text('Meta API')
        page.locator('#cloud-consent').check()
        page.get_by_label('AI route',exact=True).select_option('baseten')
        expect(page.locator('#cloud-consent')).not_to_be_checked()
        expect(page.locator('#ai-consent-description')).to_contain_text('to Baseten')
        page.get_by_role('button',name='Interpret workflow',exact=False).click()
        expect(page.locator('#studio-notice')).to_contain_text('Confirm the cloud-data operation')
        page.reload()
        page.locator('#workspace-file').set_input_files(str(FIXTURES/'meta-handoff-original.json'))
        page.locator('.cloud-options > summary').click()
        expect(page.get_by_role('region',name='AI proposal')).to_contain_text('Direct Meta API and Fireworks were not called')
        page.get_by_text('Source references used by the model',exact=False).click()
        expect(page.locator('.ai-evidence')).to_contain_text('Continuity brief.md')
        expect(page.locator('#confirm-rule')).not_to_be_checked()
        expect(page.locator('#cloud-consent')).not_to_be_checked()
        page.locator('#followup-text').fill('Confirm Northstar received the logo pack and usage guide.')
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.locator('.cloud-options').screenshot(path=str(EVIDENCE/'recorded-proposal-mobile.png'))
        assert not calls and not errors,(calls,errors)
        browser.close()
    result={'status':'passed','route_switch_clears_consent':True,'replayed_real_response':True,
        'source_references_visible':True,'proposal_still_unconfirmed':True,
        'followup_editable':True,'mobile_no_horizontal_overflow':True,'provider_requests':calls,'errors':errors}
    (EVIDENCE/'cloud-routes-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':run()
