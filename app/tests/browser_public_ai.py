"""Hosted UI denial/recovery checks with intercepted inference, never paid calls."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]
BASE=os.environ.get('EXITFORGE_TEST_URL','http://127.0.0.1:8766')
OUT=Path(os.environ['EXITFORGE_TEST_EVIDENCE'])


def run():
    OUT.mkdir(parents=True,exist_ok=True)
    errors=[];attempts=[];available=True;shared_remaining=4;session_checks=[]
    with sync_playwright() as p:
        browser=p.chromium.launch()
        context=browser.new_context(viewport={'width':1440,'height':1000})
        page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        page.route('**/api/status',lambda route:route.fulfill(json={'cloud_enabled':True,'available_routes':['baseten'],'providers':[],
                   'trial':{'shared_operations_remaining':shared_remaining},'deployment':{'mode':'public-demo','notice':'Meta via Baseten is connected.'}}))
        def session(route):
            session_checks.append(1);route.fulfill(json={'available':available,'remaining':2 if available else 0})
        page.route('**/api/ai/session',session)
        def denied(route):
            attempts.append(route.request.headers)
            route.fulfill(status=429,json={'error':'Shared trial exhausted. Continue manual review.'})
        page.route('**/api/enhance',denied)
        page.goto(BASE)
        expect(page.locator('#hosted-ai-allowance')).to_contain_text('2 operation(s)')
        page.get_by_role('button',name='Try client handoff',exact=True).click()
        page.get_by_role('button',name='Review with Meta AI',exact=True).click()
        expect(page.locator('#ai-route option[value=direct]')).to_have_attribute('disabled','')
        page.locator('#run-ai').click()
        expect(page.locator('#studio-notice')).to_contain_text('Confirm')
        assert not attempts
        page.locator('#cloud-consent').check();page.locator('#run-ai').click()
        expect(page.locator('#studio-notice')).to_contain_text('Shared trial exhausted')
        assert len(attempts)==1 and len(attempts[0]['idempotency-key'])>=16
        available=False;shared_remaining=0
        page.get_by_role('button',name='Connections',exact=True).click();page.keyboard.press('Escape')
        # Refresh rechecks the persisted session; no inference may occur.
        checks_before_reload=len(session_checks)
        page.reload();page.get_by_role('button',name='Try client handoff',exact=True).click()
        expect(page.locator('#hosted-ai-allowance')).to_contain_text('total allowance')
        assert len(session_checks)==checks_before_reload
        expect(page.locator('#run-ai')).to_be_disabled()
        page.locator('#confirm-rule').check();page.get_by_role('button',name='Confirm & open workspace',exact=True).click()
        expect(page.locator('.project-card')).to_have_count(3)
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(OUT/'quota-manual-continuation.png'),full_page=True)
        browser.close()
    assert not errors,errors
    result={'status':'passed','consent_before_request':True,'one_intercepted_request':len(attempts),'idempotency_header':True,
            'quota_visible_and_unavailable_route_disabled':True,'lifetime_exhaustion_does_not_issue_sessions_or_claim_daily_reset':True,'manual_continuation_after_exhaustion':True,'mobile_no_overflow':True,'page_errors':errors,'paid_calls':0}
    (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':run()
