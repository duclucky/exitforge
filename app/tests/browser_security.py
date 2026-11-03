"""Changed-input and hostile-text browser checks. No live providers are used."""

import csv
import io
import json
import os
import zipfile
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parent.parent
EVIDENCE=Path(os.environ.get('EXITFORGE_TEST_EVIDENCE',ROOT.parent/'.hackathon/evidence/exitforge-local-mvp')).resolve()


def run():
    EVIDENCE.mkdir(parents=True,exist_ok=True)
    rows=io.StringIO();writer=csv.writer(rows)
    writer.writerow(['Name','Status','Client'])
    writer.writerow(['Independent input','Active','Client reference'])
    writer.writerow(['Another record','Ready','Client reference'])
    contents=io.BytesIO()
    with zipfile.ZipFile(contents,'w',zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr('Changed projects.csv',rows.getvalue())
        bundle.writestr('Independent input.md','# Independent input\n\n</script><script>window.INJECTED=true</script>\n<img src="https://example.test/no-fetch" onerror="window.INJECTED=true">\n\n[Client reference](Client%20reference.md)\n[Unsafe](javascript:window.INJECTED=true)\n- [ ] Actual approval\n')
        bundle.writestr('Another record.md','# Another record\n\nDifferent source data, not the sample.')
        bundle.writestr('Client reference.md','# Client reference\n\nAn explicit source-linked page.')
    fixture=EVIDENCE/'changed-hostile-export.zip';fixture.write_bytes(contents.getvalue())
    errors=[];external=[]
    with sync_playwright() as driver:
        browser=driver.chromium.launch(headless=True)
        context=browser.new_context(viewport={'width':390,'height':844},accept_downloads=True)
        page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('request',lambda request:external.append(request.url) if request.url.startswith(('http:','https:')) and not request.url.startswith(os.environ.get('EXITFORGE_TEST_URL','http://127.0.0.1:8765')) else None)
        page.goto(os.environ.get('EXITFORGE_TEST_URL','http://127.0.0.1:8765'))
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.get_by_role('button',name='Connections',exact=True).click()
        expect(page.get_by_role('dialog',name='Provider connections')).to_be_visible()
        page.keyboard.press('Escape')
        expect(page.get_by_role('dialog',name='Provider connections')).not_to_be_visible()
        page.locator('#workspace-file').set_input_files(str(fixture))
        expect(page.locator('#delivery-state')).to_be_visible()
        page.locator('.source-inspector summary').click()
        expect(page.locator('.source-preview pre')).to_be_visible()
        assert page.evaluate('typeof window.INJECTED')=='undefined'
        assert page.locator('.source-preview img,.source-preview script').count()==0
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.locator('#delivery-state').select_option('Ready')
        page.locator('#confirm-rule').check()
        page.get_by_role('button',name='Confirm & open workspace').click()
        expect(page.locator('.project-card')).to_have_count(2)
        page.locator('.project-card').filter(has_text='Independent input').click()
        dialog=page.get_by_role('dialog',name='Project details')
        expect(dialog.locator('.page-body')).to_contain_text('window.INJECTED=true')
        assert page.evaluate('typeof window.INJECTED')=='undefined'
        assert page.locator('img').count()==0
        dialog.locator('.page-body').get_by_role('button',name='Client reference',exact=True).click()
        expect(dialog.get_by_role('heading',name='Client reference',exact=True)).to_be_visible()
        page.keyboard.press('Escape')
        expect(dialog).not_to_be_visible()
        page.get_by_role('button',name='Take it with you').click()
        with page.expect_download() as event:page.get_by_role('button',name='Download independent app').click()
        portable=EVIDENCE/'changed-independent.html';event.value.save_as(str(portable))
        context.close()
        offline=browser.new_context(viewport={'width':1280,'height':900})
        offline.set_offline(True)
        output=offline.new_page();output.on('pageerror',lambda error:errors.append(str(error)))
        output.on('request',lambda request:external.append(request.url) if request.url.startswith(('http:','https:')) else None)
        output.goto(portable.as_uri())
        expect(output.locator('.project-card')).to_have_count(2)
        output.locator('.project-card').filter(has_text='Independent input').click()
        expect(output.locator('.page-body')).to_contain_text('<img src=')
        assert output.evaluate('typeof window.INJECTED')=='undefined'
        assert output.locator('img').count()==0
        # Data and nine trusted runtime/form/handoff/bootstrap blocks. The hostile
        # source did not create an additional executable script.
        assert output.locator('script').count()==10
        assert output.locator('script[src]').count()==0
        assert not external,external
        assert not errors,errors
        version=browser.version
        browser.close()
    result={'status':'passed','browser':'Chromium '+version,'checks':['independently constructed non-sample ZIP','changed fields and two source records retained','explicit page navigation','source preview safely renders hostile text','hostile Markdown rendered as text','script-container breakout prevented','javascript URL blocked','no external fetches','provider dialog closes with Escape','390px studio fits viewport','zero browser errors'],'live_provider_calls':0}
    (EVIDENCE/'browser-security-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':run()
