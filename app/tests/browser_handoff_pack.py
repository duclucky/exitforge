"""Project-only handoff in studio, independent file and passive recipient page."""
import json
import os
from pathlib import Path
import zipfile
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
BASE=os.environ.get('EXITFORGE_TEST_URL','http://127.0.0.1:8766')
OUT=Path(os.environ.get('EXITFORGE_TEST_EVIDENCE',ROOT.parent/'.hackathon/evidence/exitforge-handoff-pack-2026-11-02/browser')).resolve()


def inspect_archive(path,folder,notes=False,assets=0):
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist())==4+assets
        assert all(not name.startswith(('/', '\\')) and '..' not in Path(name).parts for name in archive.namelist())
        content=json.loads(archive.read('records.json'));manifest=json.loads(archive.read('manifest.json'))
        assert content['project']['title']=='Brand launch' and len(content['items'])==2
        text=b'\n'.join(archive.read(name) for name in archive.namelist()).decode('utf-8')
        assert 'Cedar & Co' not in text and 'Website refresh' not in text and 'Lumen Collective' not in text
        assert 'process_review' not in text and 'cloud_calls' not in text
        assert ('notes' in content['project']) is notes and len(content['files'])==assets
        assert manifest['included']['notes'] is notes
        archive.extractall(folder)
    return folder/'index.html'


def run():
    OUT.mkdir(parents=True,exist_ok=True);errors=[];cloud=[];offline_requests=[]
    with sync_playwright() as p:
        browser=p.chromium.launch();context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True)
        page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('request',lambda request:cloud.append(request.url) if request.url.endswith(('/api/enhance','/api/reconstruct-process','/api/modal-package')) else None)
        page.goto(BASE);page.get_by_role('button',name='Rebuild a working process').click()
        page.locator('#process-parent-policy').select_option('Changes requested');page.locator('#confirm-process').check();page.locator('#open-process').click()
        expect(page.get_by_role('button',name='Client handoff',exact=True)).to_be_visible()
        page.get_by_role('button',name='Client handoff',exact=True).click();dialog=page.get_by_role('dialog',name='Client handoff preview')
        expect(dialog.locator('[data-handoff-eligibility]')).to_contain_text('Logo pack must be Approved')
        expect(dialog.get_by_role('button',name='Download handoff ZIP',exact=True)).not_to_be_enabled()
        expect(dialog.get_by_label('Include working notes',exact=True)).not_to_be_checked()
        assert dialog.locator('[data-handoff-asset]:checked').count()==0
        dialog.get_by_role('button',name='Close preview',exact=True).click()
        page.locator('.linked-item').filter(has_text='Logo pack').get_by_role('button',name='Mark Approved',exact=True).click()
        page.get_by_role('button',name='Client handoff',exact=True).click();dialog=page.get_by_role('dialog',name='Client handoff preview')
        expect(dialog.locator('[data-handoff-eligibility]')).to_contain_text('Hand over this project first')
        dialog.get_by_role('button',name='Close preview',exact=True).click();page.get_by_role('button',name='Hand over',exact=True).click()
        page.get_by_role('button',name='Client handoff',exact=True).click();dialog=page.get_by_role('dialog',name='Client handoff preview')
        expect(dialog.locator('[data-handoff-eligibility]')).to_contain_text('Ready')
        page.screenshot(path=str(OUT/'01-ready-preview.png'))
        with page.expect_download() as event:dialog.get_by_role('button',name='Download handoff ZIP',exact=True).click()
        minimal=OUT/'minimal.zip';event.value.save_as(str(minimal));inspect_archive(minimal,OUT/'minimal')
        dialog.get_by_role('button',name='Close preview',exact=True).click()
        page.locator('.linked-item').filter(has_text='Logo pack').get_by_role('button',name='Request changes',exact=True).click()
        page.get_by_role('button',name='Client handoff',exact=True).click();dialog=page.get_by_role('dialog',name='Client handoff preview')
        expect(dialog.get_by_role('button',name='Download handoff ZIP',exact=True)).not_to_be_enabled()
        expect(dialog.get_by_label('Include working notes',exact=True)).not_to_be_checked()
        dialog.get_by_role('button',name='Close preview',exact=True).click()
        page.locator('.linked-item').filter(has_text='Logo pack').get_by_role('button',name='Mark Approved',exact=True).click()
        page.get_by_role('button',name='Hand over',exact=True).click()
        page.get_by_role('button',name='Take it with you',exact=True).click()
        with page.expect_download() as event:page.get_by_role('button',name='Download independent app').click()
        artifact=OUT/'independent.html';event.value.save_as(str(artifact));context.close()
        context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True);context.set_offline(True);page=context.new_page()
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('request',lambda request:offline_requests.append(request.url) if request.url.startswith(('http:','https:')) else None)
        page.goto(artifact.as_uri());page.get_by_role('button',name='Client handoff',exact=True).click()
        dialog=page.get_by_role('dialog',name='Client handoff preview');dialog.get_by_label('Include working notes',exact=True).check()
        dialog.locator('[data-handoff-asset]').check();expect(dialog.locator('[data-handoff-notes]')).to_contain_text('Brand launch')
        page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(OUT/'02-mobile-explicit-selection.png'))
        with page.expect_download() as event:dialog.get_by_role('button',name='Download handoff ZIP',exact=True).click()
        full=OUT/'selected.zip';event.value.save_as(str(full));index=inspect_archive(full,OUT/'selected',True,1)
        context.close();context=browser.new_context(viewport={'width':1440,'height':1000},accept_downloads=True);context.set_offline(True);page=context.new_page()
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('request',lambda request:offline_requests.append(request.url) if request.url.startswith(('http:','https:')) else None)
        page.goto(index.as_uri());expect(page.get_by_role('heading',name='Brand launch',exact=True)).to_be_visible()
        assert page.locator('script,form,iframe').count()==0
        expect(page.get_by_text('Northstar Studio',exact=True)).to_be_visible()
        page.get_by_role('link',name='handoff-note.txt',exact=True).click()
        assert page.url.endswith('/files/001-handoff-note.txt')
        expect(page.locator('body')).to_contain_text((OUT/'selected/files/001-handoff-note.txt').read_text(encoding='utf-8').strip())
        page.go_back()
        page.screenshot(path=str(OUT/'03-passive-recipient.png'),full_page=True)
        context.close();browser.close()
    assert not errors and not cloud and not offline_requests,(errors,cloud,offline_requests)
    result={'status':'passed','project_only_scope':True,'default_no_notes_or_attachments':True,'eligibility_before_download':True,'actual_offline_zip_creation':True,'cross_language_crc_and_extraction':True,'passive_recipient_html_and_local_file_access':True,'mobile_preview_no_overflow':True,'new_live_calls':0,'page_errors':errors,'offline_http_requests':offline_requests}
    (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))


if __name__=='__main__':run()
