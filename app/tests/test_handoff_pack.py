"""Decode actual browser-format ZIP bytes with Python's independent ZIP reader."""
import base64
import copy
import io
import json
from pathlib import Path
import subprocess
import unittest
import zipfile


class HandoffArchiveTests(unittest.TestCase):
    def test_zip_crc_unicode_and_hostile_notes_are_interoperable_and_passive(self):
        data=json.loads(Path('tests/fixtures/process-delivery.json').read_text(encoding='utf-8'));p=data['process'];parent_id=p['links'][0]['parent']
        parent=next(page for page in data['pages'] if page['id']==parent_id)
        parent['properties'][p['parent_field']]='Delivered';parent['title']='Mùa xuân <script>alert(1)</script>'
        parent['body']='A private note: </pre><img src="https://attacker.invalid/pixel"><script>window.INJECTED=true</script>'
        for link in p['links']:
            if link['parent']==parent_id:next(page for page in data['pages'] if page['id']==link['child'])['properties'][p['child_field']]='Approved'
        asset_id=parent['attachments'][0];asset=data['assets'][asset_id];asset['name']='đơn 你好".txt';raw=b'\x00\xff\x10Binary-safe ZIP fixture\n';asset['data']=base64.b64encode(raw).decode()
        original=copy.deepcopy(data)
        script="const fs=require('node:fs');const x=JSON.parse(fs.readFileSync(0,'utf8'));const r=require('./static/handoff.js').build(x.data,x.parent,{includeNotes:true,assetIds:[x.asset]},'2026-11-02T12:00:00.000Z');process.stdout.write(Buffer.from(r.bytes).toString('base64'));"
        run=subprocess.run(['node','-e',script],input=json.dumps({'data':data,'parent':parent_id,'asset':asset_id}),capture_output=True,text=True,check=True)
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(run.stdout))) as archive:
            self.assertIsNone(archive.testzip());self.assertEqual(len(archive.infolist()),5)
            self.assertTrue(all(info.compress_type==zipfile.ZIP_STORED and info.flag_bits&0x800 for info in archive.infolist()))
            records=json.loads(archive.read('records.json'));file=records['files'][0]
            self.assertEqual(archive.read(file['path']),raw);self.assertIn('đơn 你好_',file['path'])
            html=archive.read('index.html').decode('utf-8')
            self.assertNotIn('<script',html);self.assertNotIn('<img',html);self.assertIn('&lt;script&gt;',html)
            self.assertNotIn('Cedar &amp; Co',html);self.assertNotIn('Website refresh',html)
            self.assertIn("default-src 'none'",html);self.assertNotIn('<form',html)
            self.assertEqual(json.loads(archive.read('manifest.json'))['included']['projects'],1)
            self.assertEqual(archive.namelist()[0],'manifest.json')
            self.assertEqual(set(json.loads(archive.read('manifest.json'))['contents']),set(archive.namelist()))
        self.assertEqual(data,original)


if __name__=='__main__':unittest.main()
