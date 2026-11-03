"""Real local/offline foundation journeys; never uses the user's browser or cloud."""

import io
import json
import os
import re
from pathlib import Path
import sys
import threading
import zipfile
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright, expect

APP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP))
from exitforge.server import Handler
from exitforge.importer import recover_archive
from exitforge.sample import sample_archive

EVIDENCE = Path(os.environ.get('EXITFORGE_TEST_EVIDENCE', APP.parent / '.hackathon/evidence/exitforge-foundation')).resolve()
EVIDENCE.mkdir(parents=True, exist_ok=True)


def run():
    errors, external, cloud = [], [], []
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        with sync_playwright() as driver:
            browser = driver.chromium.launch(headless=True)
            context = browser.new_context(viewport={'width': 1440, 'height': 1000}, accept_downloads=True)
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('request', lambda req: external.append(req.url) if req.url.startswith(('http:', 'https:')) and not req.url.startswith(base+'/') else None)
            page.on('request', lambda req: cloud.append(req.url) if '/api/enhance' in req.url or '/api/modal-package' in req.url else None)
            page.goto(base)
            page.get_by_role('button', name='Try sample workspace').click()
            expect(page.get_by_role('heading', name='Declare your delivery workflow')).to_be_visible()
            page.locator('#workspace-name').fill('My recovered workspace')
            page.locator('#followup-text').fill('Verify the handoff')
            page.locator('.cloud-options summary').click()
            page.locator('#cloud-consent').check()
            page.reload()
            page.get_by_role('button', name='Resume saved workspace').click()
            expect(page.locator('#workspace-name')).to_have_value('My recovered workspace')
            expect(page.locator('#followup-text')).to_have_value('Verify the handoff')
            expect(page.locator('#cloud-consent')).not_to_be_checked()
            expect(page.locator('#confirm-rule')).not_to_be_checked()
            page.locator('#confirm-rule').check()
            page.get_by_role('button', name='Confirm & open workspace').click()
            expect(page.locator('.project-card')).to_have_count(30)
            page.locator('.project-card').filter(has=page.locator('strong', has_text=re.compile('^Brand launch$'))).click()
            dialog = page.get_by_role('dialog', name='Project details')
            dialog.locator('summary').click()
            dialog.get_by_label('Notes (Markdown)').fill('# Brand launch\n\nFoundation draft edit.')
            dialog.get_by_role('button', name='Save notes').click()
            dialog.get_by_role('checkbox', name='Get final approval').check()
            dialog.get_by_label('Project status').select_option('Delivered')
            dialog.get_by_role('button', name='Close project details').click()
            page.reload()
            page.screenshot(path=str(EVIDENCE/'01-resume-draft.png'), full_page=True)
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.screenshot(path=str(EVIDENCE/'01b-mobile-resume.png'), full_page=True)
            page.set_viewport_size({'width':1440,'height':1000})
            page.get_by_role('button', name='Resume saved workspace').click()
            page.locator('.project-card').filter(has=page.locator('strong', has_text=re.compile('^Brand launch$'))).click()
            expect(page.locator('.page-body')).to_contain_text('Foundation draft edit.')
            expect(page.get_by_label('Project status')).to_have_value('Delivered')
            page.get_by_role('button', name='Close project details').click()
            page.get_by_role('button', name='Follow-ups', exact=False).click()
            page.get_by_label('Find a project or page').fill('Verify')
            page.locator('[data-task]').check()
            page.reload()
            page.get_by_role('button', name='Resume saved workspace').click()
            page.get_by_role('button', name='Follow-ups', exact=False).click()
            expect(page.locator('[data-task]')).to_be_checked()

            # Independently extend the archive with a second CSV, rather than rely on the sample UI.
            archive = io.BytesIO(sample_archive())
            with zipfile.ZipFile(archive, 'a') as bundle:
                bundle.writestr('Operations.csv', 'Name,Status\nLaunch operations,Backlog\n')
            project = recover_archive(archive.getvalue(), 'two-databases.zip')
            backup = EVIDENCE/'two-databases.json'
            backup.write_text(json.dumps(project), encoding='utf-8')
            page.locator('[data-step="0"]').click()
            page.locator('#workspace-file').set_input_files(str(backup))
            page.locator('#confirm-rule').check()
            page.get_by_role('button', name='Confirm & open workspace').click()
            second = next(db for db in project['databases'] if db['title'] == 'Operations')
            page.get_by_label('Active database').select_option(second['id'])
            expect(page.locator('.project-card')).to_have_count(1)
            expect(page.locator('.project-card')).to_contain_text('Launch operations')
            page.screenshot(path=str(EVIDENCE/'02-selected-database.png'), full_page=True)
            page.get_by_role('button', name='Take it with you').click()
            with page.expect_download() as event:
                page.get_by_role('button', name='Download independent app').click()
            portable = EVIDENCE/'foundation-independent.html'
            event.value.save_as(str(portable))

            offline = browser.new_context(viewport={'width': 1440, 'height': 1000}, accept_downloads=True)
            offline.set_offline(True)
            filepage = offline.new_page()
            filepage.on('pageerror', lambda error: errors.append(str(error)))
            filepage.on('request', lambda req: external.append(req.url) if req.url.startswith(('http:', 'https:')) else None)
            filepage.goto(portable.as_uri())
            expect(filepage.get_by_label('Active database')).to_have_value(second['id'])
            expect(filepage.locator('.project-card')).to_have_count(1)
            with filepage.expect_download() as event:
                filepage.get_by_role('button', name='Data backup', exact=True).click()
            current = EVIDENCE/'portable-current-data.json'
            event.value.save_as(str(current))
            restored = json.loads(current.read_text(encoding='utf-8'))
            operation = next(item for item in restored['pages'] if item['id'] == second['rows'][0])
            operation['properties']['Status'] = 'Archived after export'
            changed = EVIDENCE/'changed-state.json'
            changed.write_text(json.dumps(restored), encoding='utf-8')
            filepage.locator('[data-restore]').set_input_files(str(changed))
            expect(filepage.locator('.runtime-notice')).to_contain_text('Workspace restored')
            expect(filepage.locator('.project-card')).to_have_count(1)
            expect(filepage.locator('.board-column').filter(has_text='Other / unassigned')).to_have_count(1)
            filepage.reload()
            expect(filepage.locator('.project-card')).to_have_count(1)
            expect(filepage.get_by_label('Active database')).to_have_value(second['id'])

            # Rejected attachment input must not replace the working state.
            restored['assets']['bad'] = {'name':'attack.html','mime':'text/html','data':'eA=='}
            operation['attachments'].append('bad')
            invalid = EVIDENCE/'invalid-attachment-backup.json'
            invalid.write_text(json.dumps(restored), encoding='utf-8')
            filepage.locator('[data-restore]').set_input_files(str(invalid))
            expect(filepage.locator('.runtime-notice')).to_contain_text('invalid attachment')
            expect(filepage.locator('.project-card')).to_have_count(1)
            filepage.screenshot(path=str(EVIDENCE/'03-rejected-backup-offline.png'), full_page=True)
            wrong = json.loads(current.read_text(encoding='utf-8'))
            wrong['id'] = 'different-workspace'
            wrong_file = EVIDENCE/'wrong-workspace.json'
            wrong_file.write_text(json.dumps(wrong), encoding='utf-8')
            filepage.locator('[data-restore]').set_input_files(str(wrong_file))
            expect(filepage.locator('.runtime-notice')).to_contain_text('Choose a data backup for this workspace')
            expect(filepage.locator('.project-card')).to_have_count(1)
            filepage.evaluate("id=>localStorage.setItem('exitforge.workspace.v1.'+id,JSON.stringify({schema_version:1,id,pages:[{}]}))", project['id'])
            filepage.reload()
            expect(filepage.locator('.runtime-notice')).to_contain_text('Saved browser data could not be used')
            expect(filepage.locator('.project-card')).to_have_count(1)
            filepage.set_viewport_size({'width':390,'height':844})
            assert filepage.evaluate('document.documentElement.scrollWidth <= innerWidth')
            filepage.screenshot(path=str(EVIDENCE/'04-mobile-offline.png'), full_page=True)
            offline.close()

            # Storage failure must be visible, while current data can still be backed up.
            blocked = browser.new_context()
            blocked.add_init_script("Storage.prototype.setItem = function(){throw new DOMException('Full','QuotaExceededError');};")
            blocked_page = blocked.new_page()
            blocked_page.goto(base)
            blocked_page.get_by_role('button', name='Try sample workspace').click()
            expect(blocked_page.locator('#draft-status')).to_contain_text('Download a data backup')
            with blocked_page.expect_download() as event:
                blocked_page.get_by_role('button', name='Back up current workspace', exact=True).click()
            event.value.save_as(str(EVIDENCE/'quota-fallback-backup.json'))
            assert len(json.loads((EVIDENCE/'quota-fallback-backup.json').read_text(encoding='utf-8'))['pages']) == 33
            blocked.close()

            page.locator('[data-step="0"]').click()
            page.get_by_role('button', name='Remove saved draft', exact=True).click()
            page.reload()
            expect(page.get_by_role('button', name='Resume saved workspace')).to_have_count(0)
            context.close()
            browser.close()
    finally:
        server.shutdown(); server.server_close(); thread.join()
    assert not errors, errors
    assert not external, external
    assert not cloud, cloud
    result={'review_draft_survives_reload':True,'consent_not_restored':True,'edited_draft_survives_reload':True,
            'independent_database_fixture':True,'database_selection_survives_export_reload':True,
            'unknown_states_remain_visible':True,'unsafe_backup_rejected_without_data_loss':True,
            'cross_workspace_backup_rejected':True,'corrupt_browser_state_falls_back_to_packaged_snapshot':True,
            'followup_toggle_after_search_persists':True,
            'studio_and_offline_mobile_no_overflow':True,'quota_fallback_backup_downloaded':True,'explicit_draft_removal':True,
            'javascript_errors':errors,'external_requests':external,'cloud_requests':cloud}
    (EVIDENCE/'browser-foundation-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    run()
