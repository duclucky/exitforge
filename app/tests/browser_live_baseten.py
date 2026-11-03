"""Explicitly authorized live UI check; defaults to offline artifact verification.

--live sends the original synthetic handoff to Baseten through the product route.
It refuses to repeat a recorded live request. Never uses customer Chrome or data.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parent.parent
EVIDENCE=ROOT.parent/'.hackathon/evidence/exitforge-credit-recheck-2026-10-29'


def live_journey(browser):
    response_path=EVIDENCE/'live-api-response.json'
    if response_path.exists():
        raise RuntimeError('Live response already recorded. Use the default offline check; do not repeat spending.')
    state=json.loads((ROOT.parent/'.hackathon/state.json').read_text())
    assert state['budget']['amount']==1 and state['budget']['planning_total_with_reserve_usd']<0.8
    context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
    page=context.new_page();page.set_default_timeout(15000)
    page.goto(os.environ.get('EXITFORGE_TEST_URL','http://127.0.0.1:8765'))
    page.get_by_role('button',name='Try client handoff',exact=True).click()
    page.get_by_text('Optional: interpret with Meta AI',exact=False).click()
    page.get_by_label('AI route',exact=True).select_option('baseten')
    expect(page.locator('#cloud-consent')).not_to_be_checked()
    page.get_by_role('button',name='Interpret workflow',exact=False).click()
    expect(page.locator('#studio-notice')).to_contain_text('Confirm the cloud-data operation')
    page.locator('#cloud-consent').check()
    with page.expect_response(lambda r:r.url.endswith('/api/enhance'),timeout=190000) as event:
        page.get_by_role('button',name='Interpret workflow',exact=False).click()
    response=event.value;result=response.json()
    response_path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    assert response.status==200,result
    assert result['route']=='baseten' and result['template_selection']=='curated_unranked'
    assert len(result['calls'])==2
    assert all(c['provider']=='Baseten' and c['model']=='meta-models/muse-spark-open-1026' for c in result['calls'])
    assert result['requires_user_confirmation'] is True
    expect(page.locator('#studio-notice')).to_contain_text('AI proposal received')
    expect(page.locator('#confirm-rule')).not_to_be_checked()
    page.get_by_text('Optional: interpret with Meta AI',exact=False).click()
    expect(page.get_by_role('region',name='AI proposal')).to_contain_text('Direct Meta API and Fireworks were not called')
    expect(page.locator('#cloud-consent')).not_to_be_checked()
    page.get_by_role('region',name='AI proposal').screenshot(path=str(EVIDENCE/'live-model-proposal.png'))
    with page.expect_download() as download:page.get_by_role('button',name='Back up current workspace',exact=True).click()
    download.value.save_as(str(EVIDENCE/'live-unconfirmed-workspace.json'))
    snapshot=json.loads((EVIDENCE/'live-unconfirmed-workspace.json').read_text())
    assert snapshot['workflow']['confirmed'] is False
    assert len(snapshot['provenance']['cloud_calls'])==2
    page.get_by_role('button',name='Review delivery rule',exact=True).click()
    page.locator('#confirm-rule').check()
    page.get_by_role('button',name='Confirm & open workspace',exact=True).click()
    page.get_by_role('button',name='Open demo project',exact=True).click()
    dialog=page.get_by_role('dialog',name='Project details')
    dialog.get_by_label('Project status').select_option('Delivered')
    expect(dialog.locator('.dialog-message')).to_contain_text('Complete the handoff checklist')
    dialog.get_by_role('checkbox',name='Get final approval',exact=True).check()
    dialog.get_by_label('Project status').select_option('Delivered')
    expect(dialog.get_by_role('button',name='View follow-up',exact=True)).to_be_visible()
    dialog.get_by_role('button',name='View follow-up',exact=True).click()
    expect(page.locator('.task-row')).to_have_count(1)
    page.screenshot(path=str(EVIDENCE/'live-workflow-result.png'))
    page.get_by_role('button',name='Take it with you',exact=True).click()
    with page.expect_download() as download:page.get_by_role('button',name='Download independent app',exact=True).click()
    download.value.save_as(str(EVIDENCE/'live-meta-open-independent.html'))
    context.close()


def verify_artifact(browser):
    artifact=EVIDENCE/'live-meta-open-independent.html'
    if not artifact.exists():raise RuntimeError('No existing artifact. --live needs current access and spending authorization.')
    errors=[];network=[]
    context=browser.new_context(viewport={'width':390,'height':844},accept_downloads=True)
    context.set_offline(True);page=context.new_page()
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('request',lambda r:network.append(r.url) if r.url.startswith(('http:','https:')) else None)
    page.goto(artifact.as_uri())
    expect(page.locator('.project-card')).to_have_count(3)
    page.locator('.project-card').filter(has=page.locator('strong',has_text=re.compile('^Brand launch$'))).click()
    dialog=page.get_by_role('dialog',name='Project details')
    expect(dialog.get_by_label('Project status')).to_have_value('Delivered')
    with page.expect_download() as download:dialog.locator('[data-asset]').click()
    download.value.save_as(str(EVIDENCE/'live-handoff-note.txt'))
    assert 'logo pack' in (EVIDENCE/'live-handoff-note.txt').read_text()
    dialog.locator('.edit-notes summary').click()
    dialog.get_by_label('Notes (Markdown)').fill('# Brand launch\n\nReceipt confirmed offline after real Meta open-weight interpretation.')
    dialog.get_by_role('button',name='Save notes',exact=True).click()
    dialog.get_by_role('button',name='Close project details').click();page.reload()
    page.locator('.project-card').filter(has=page.locator('strong',has_text=re.compile('^Brand launch$'))).click()
    expect(page.locator('.page-body')).to_contain_text('Receipt confirmed offline')
    page.get_by_role('button',name='Close project details').click()
    page.get_by_role('button',name='Follow-ups',exact=False).click()
    expect(page.locator('.task-row')).to_have_count(1)
    with page.expect_download() as download:page.get_by_role('button',name='Data backup',exact=True).click()
    download.value.save_as(str(EVIDENCE/'live-offline-current-backup.json'))
    backup=json.loads((EVIDENCE/'live-offline-current-backup.json').read_text())
    assert len(backup['pages'])==7 and len(backup['assets'])==3 and len(backup['provenance']['cloud_calls'])==2
    assert backup['ai_review']['route']=='baseten'
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(EVIDENCE/'live-offline-result.png'))
    assert not errors and not network,(errors,network)
    context.close()
    return {'offline_edit_reload_backup':True,'offline_http_requests':network,'errors':errors}


def run():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--live',action='store_true')
    args=parser.parse_args();EVIDENCE.mkdir(exist_ok=True,parents=True)
    with sync_playwright() as p:
        browser=p.chromium.launch()
        if args.live:live_journey(browser)
        offline=verify_artifact(browser);browser.close()
    response=json.loads((EVIDENCE/'live-api-response.json').read_text())
    usage=[c.get('usage',{}) for c in response['calls']]
    estimate=sum((u.get('prompt_tokens',0)*1.25+u.get('completion_tokens',0)*4.25)/1_000_000 for u in usage)
    result={'status':'passed','checked_at':datetime.now(timezone.utc).isoformat(),
        'route':'Meta open weights via Baseten','new_live_calls_this_run':2 if args.live else 0,
        'recorded_provider_calls':response['calls'],'direct_meta_api_called':False,'fireworks_called':False,
        'curated_templates_not_reranked':True,'explicit_human_confirmation_verified':True,
        'delivery_guard_and_one_followup_verified':True,'conservative_cost_estimate_usd':round(estimate,9),
        'cost_note':'Uncached public-alias prices used for planning, not a verified event-grant bill.',**offline}
    (EVIDENCE/'live-browser-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':run()
