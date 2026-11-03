/* Project-scoped disclosure and passive handoff files; no workspace serialization. */
(function(global){
  'use strict';
  const encoder=new TextEncoder(),limit=16*1024*1024;
  const workspace=()=>typeof module!=='undefined'&&module.exports?require('./workspace.js'):global.ExitForgeWorkspace;
  const engine=()=>typeof module!=='undefined'&&module.exports?require('./process.js'):global.ExitForgeProcess;
  const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function check(ok,message){if(!ok)throw new Error(message);}
  function preview(data,parentId,options={}){
    workspace().validateWorkspace(data);const p=data.process;
    check(p&&data.databases.find(db=>db.id===p.parent_db).rows.includes(parentId),'Choose a project from the reviewed linked process.');
    check(options&&typeof options==='object'&&!Array.isArray(options)&&Object.keys(options).every(key=>['includeNotes','assetIds'].includes(key)),'Unsupported handoff selection.');
    check(options.includeNotes===undefined||typeof options.includeNotes==='boolean','Choose whether to include working notes.');
    const assetIds=options.assetIds??[];
    check(Array.isArray(assetIds)&&assetIds.length<=100&&assetIds.every(id=>typeof id==='string')&&new Set(assetIds).size===assetIds.length,'Choose up to 100 distinct attached files.');
    const parent=data.pages.find(page=>page.id===parentId),children=engine().related(data,parentId),selected=[parent,...children];
    const availableIds=[...new Set(selected.flatMap(page=>page.attachments))];
    check(assetIds.every(id=>availableIds.includes(id)),'An attachment belongs outside the selected project.');
    const available=availableIds.map(id=>({id,name:data.assets[id].name,mime:data.assets[id].mime,bytes:atob(data.assets[id].data).length}));
    const state=p.actions.find(action=>action.kind==='handover_parent').to;
    const reasons=[...(!p.confirmed?['Confirm the process before preparing a client handoff.']:[]),...engine().blockers(data,parentId),
      ...(parent.properties[p.parent_field]!==state?['Hand over this project first in the reviewed application.']:[])];
    const note=page=>options.includeNotes?{notes:page.body}:{};
    return {eligible:!reasons.length,reasons,available,selection:{includeNotes:options.includeNotes===true,assetIds:[...assetIds]},
      sample:data.provenance.sample===true,
      project:{id:parent.id,title:parent.title,client:parent.properties.Client?.trim()||parent.properties.Customer?.trim()||'Unassigned client',state:parent.properties[p.parent_field]||'',...note(parent)},
      items:children.map(page=>({id:page.id,title:page.title,state:page.properties[p.child_field]||'',...note(page)})),
      files:available.filter(file=>assetIds.includes(file.id))};
  }
  function filePath(name,index){
    const dot=name.lastIndexOf('.'),extension=name.slice(dot).toLowerCase();
    const stem=Array.from(name.slice(0,dot).normalize('NFC')).map(c=>/^[\\/:*?"<>|\x00-\x1f\x7f]$/.test(c)||(c.codePointAt(0)>=0xd800&&c.codePointAt(0)<=0xdfff)?'_':c).slice(0,70).join('').replace(/[. ]+$/,'');
    return 'files/'+String(index+1).padStart(3,'0')+'-'+(stem||'attachment')+extension;
  }
  function recipient(view,at,files){
    const e=escape;
    return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"><title>${e(view.project.title)} · Client handoff</title><style>
      *{box-sizing:border-box}body{margin:0;background:#f8f7ef;color:#141414;font:16px/1.6 Arial,sans-serif}main{max-width:980px;margin:auto;padding:40px 24px}header{border-bottom:3px solid #141414;padding-bottom:24px}.tag{display:inline-block;background:#ffe000;border:2px solid;padding:6px 12px;font:12px monospace}h1{font-size:clamp(30px,6vw,56px);line-height:1.1;margin:24px 0;overflow-wrap:anywhere}h2{font-size:26px}p,pre,dd{overflow-wrap:anywhere}.notice{padding:12px 0;font-size:13px;color:#3b3b3b}.sample{display:inline-block;background:#ffe000;font:12px monospace;padding:6px 10px}.summary span{background:white}.summary{display:flex;flex-wrap:wrap;gap:12px;margin:24px 0}.summary span{padding:10px 16px;border:1px solid}article{padding:20px 0;border-top:1px solid #888}article h3{font-size:22px;margin:5px 0}.state{font:12px monospace}.notes{white-space:pre-wrap;padding:18px;background:white;border:1px solid #bbb;font:14px/1.6 monospace}a{color:#141414;text-underline-offset:4px}a:focus-visible{outline:3px solid #3453f5;outline-offset:5px}li{margin:12px 0}footer{margin-top:40px;border-top:2px solid;padding-top:18px;font-size:12px}@media print{body{background:white}main{padding:0}.tag{background:white}article{break-inside:avoid}}
      </style></head><body><main><header><span class="tag">EXITFORGE · CLIENT HANDOFF</span><h1>${e(view.project.title)}</h1><p>Prepared for <strong>${e(view.project.client)}</strong></p><p>Snapshot: ${e(at)}</p>${view.sample?'<p class="sample">FICTIONAL DEMONSTRATION DATA</p>':''}</header>
      <div class="summary"><span>${view.items.length} linked items</span><span>${files.length} selected files</span><span>Project state: ${e(view.project.state)}</span></div>
      <p class="notice">A read-only handoff prepared from the sender’s local workflow records.</p>
      ${Object.hasOwn(view.project,'notes')?`<section><h2>Project notes</h2><pre class="notes">${e(view.project.notes)}</pre></section>`:''}
      <section><h2>Included work</h2>${view.items.map(item=>`<article><span class="state">RECORDED STATE · ${e(item.state)}</span><h3>${e(item.title)}</h3>${Object.hasOwn(item,'notes')?`<pre class="notes">${e(item.notes)}</pre>`:''}</article>`).join('')}</section>
      <section><h2>Selected files</h2>${files.length?`<ul>${files.map(file=>`<li><a href="${file.path.split('/').map(encodeURIComponent).join('/')}">${e(file.name)}</a> · ${file.bytes} bytes</li>`).join('')}</ul>`:'<p>No attached files were selected.</p>'}</section>
      <footer>Prepared with ExitForge · Read-only offline snapshot. Extract the ZIP before opening this page. Statuses reflect the preparer’s local workflow.</footer></main></body></html>`;
  }
  const crcTable=Array.from({length:256},(_,n)=>{let c=n;for(let i=0;i<8;i++)c=(c&1)?0xedb88320^(c>>>1):c>>>1;return c>>>0;});
  function crc32(bytes){let value=0xffffffff;for(const byte of bytes)value=crcTable[(value^byte)&255]^(value>>>8);return (value^0xffffffff)>>>0;}
  function join(parts){const bytes=new Uint8Array(parts.reduce((n,p)=>n+p.length,0));let at=0;for(const part of parts){bytes.set(part,at);at+=part.length;}return bytes;}
  function zip(files,at){
    // ZIP_STORED with UTF-8 names and CRC32; bounded below ZIP64 sizes.
    const local=[],central=[];let offset=0;
    const stamp=new Date(at),year=Math.max(1980,Math.min(2107,stamp.getUTCFullYear()));
    const date=((year-1980)<<9)|((stamp.getUTCMonth()+1)<<5)|stamp.getUTCDate();
    const time=(stamp.getUTCHours()<<11)|(stamp.getUTCMinutes()<<5)|(stamp.getUTCSeconds()>>1);
    for(const file of files){
      const name=encoder.encode(file.path),crc=crc32(file.bytes),header=new Uint8Array(30),view=new DataView(header.buffer);
      view.setUint32(0,0x04034b50,true);view.setUint16(4,20,true);view.setUint16(6,0x800,true);
      view.setUint16(10,time,true);view.setUint16(12,date,true);view.setUint32(14,crc,true);view.setUint32(18,file.bytes.length,true);view.setUint32(22,file.bytes.length,true);view.setUint16(26,name.length,true);
      local.push(header,name,file.bytes);
      const entry=new Uint8Array(46),v=new DataView(entry.buffer);v.setUint32(0,0x02014b50,true);v.setUint16(4,20,true);v.setUint16(6,20,true);v.setUint16(8,0x800,true);
      v.setUint16(12,time,true);v.setUint16(14,date,true);v.setUint32(16,crc,true);v.setUint32(20,file.bytes.length,true);v.setUint32(24,file.bytes.length,true);v.setUint16(28,name.length,true);v.setUint32(42,offset,true);
      central.push(entry,name);offset+=header.length+name.length+file.bytes.length;
    }
    const size=central.reduce((n,p)=>n+p.length,0),end=new Uint8Array(22),v=new DataView(end.buffer);
    v.setUint32(0,0x06054b50,true);v.setUint16(8,files.length,true);v.setUint16(10,files.length,true);v.setUint32(12,size,true);v.setUint32(16,offset,true);
    check(offset+size+22<=limit,'The handoff exceeds 16 MB. Leave out working notes or attached files.');
    return join([...local,...central,end]);
  }
  function build(data,parentId,options={},at=new Date().toISOString()){
    const view=preview(data,parentId,options);check(view.eligible,'Handoff blocked: '+view.reasons.join(' '));
    check(typeof at==='string'&&Number.isFinite(Date.parse(at))&&new Date(at).toISOString()===at,'A valid snapshot time is required.');
    const files=view.files.map((file,index)=>({name:file.name,path:filePath(file.name,index),mime:file.mime,bytes:file.bytes}));
    const records={project:view.project,items:view.items,files};
    const manifest={format:'exitforge-project-handoff',version:1,prepared_at:at,sample:view.sample,project_id:parentId,
      included:{projects:1,items:view.items.length,notes:view.selection.includeNotes,attachments:files.length},
      contents:['manifest.json','index.html','records.json','README.txt',...files.map(file=>file.path)],
      limits:['Local states are not client approval, receipt or signature.','Selected text and files are not automatically redacted.','This archive is not encrypted. No external delivery was performed.']};
    const file=(path,text)=>({path,bytes:encoder.encode(text)});
    const entries=[file('manifest.json',JSON.stringify(manifest,null,2)+'\n'),file('index.html',recipient(view,at,files)),file('records.json',JSON.stringify(records,null,2)+'\n'),
      file('README.txt','Extract this ZIP and open index.html in a browser.\nThis read-only snapshot contains one selected project and its linked items.\nNo account or network connection is needed. No workspace history or AI review is included.\nWorking notes and selected files are not automatically redacted. This archive is not encrypted.\nStates are local records, not proof of client approval, receipt or signature.\nNo message or client delivery was sent by ExitForge.\n'),
      ...view.files.map((source,index)=>({path:files[index].path,bytes:Uint8Array.from(atob(data.assets[source.id].data),c=>c.charCodeAt(0))}))];
    check(entries.reduce((n,f)=>n+f.bytes.length,0)<=limit,'The handoff exceeds 16 MB. Leave out working notes or attached files.');
    const filename=(view.project.title.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'').slice(0,60)||'project')+'-handoff.zip';
    return {bytes:zip(entries,at),manifest,records,filename};
  }
  const api={preview,build};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else global.ExitForgeHandoff=api;
})(typeof window!=='undefined'?window:globalThis);
