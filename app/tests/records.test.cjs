const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const records=require('../static/process-records.js');
const engine=require('../static/process.js');
const {validateWorkspace,recoveryReceipt}=require('../static/workspace.js');
const stamp='2026-11-02T10:00:00.000Z';
const load=(domain='delivery')=>JSON.parse(fs.readFileSync(path.join(__dirname,'fixtures','process-'+domain+'.json'),'utf8'));
const input=(role,title,initial_state,parent)=>({role,title,initial_state,parent,body:'New work after migration.',properties:role==='parent'?{Client:'Atlas Design'}:{}});

for(const domain of ['delivery','editorial'])test(domain+': create and edit work atomically, then execute the original process',()=>{
  const original=load(domain),before=structuredClone(original),raw=structuredClone(original.process);
  const project=records.create(original,input('parent','Next campaign',records.initialStates(original,'parent')[0]),'local-project',stamp);
  assert.deepEqual(original,before);assert.equal(project.workspace.pages.length,original.pages.length+1);
  assert.match(engine.blockers(project.workspace,project.recordId)[0],/No linked/);
  const first=records.create(project.workspace,input('child','Artwork',records.initialStates(project.workspace,'child')[0],project.recordId),'local-artwork',stamp);
  const second=records.create(first.workspace,input('child','Copy',records.initialStates(first.workspace,'child')[0],project.recordId),'local-copy',stamp);
  const next=records.edit(second.workspace,project.recordId,{title:'Next campaign v2',body:'Current brief.',properties:{Client:'Atlas Collective'}},stamp).workspace;
  assert.equal(next.pages.find(p=>p.id===project.recordId).properties.Name,'Next campaign v2');
  assert.deepEqual(next.process.actions,raw.actions);assert.deepEqual(next.process.links.slice(0,raw.links.length),raw.links);
  const approve=raw.actions.find(a=>a.kind==='approve_child').id,handover=raw.actions.find(a=>a.kind==='handover_parent').id;
  const blocked=structuredClone(next);assert.throws(()=>engine.execute(next,project.recordId,handover),/blocked/);assert.deepEqual(next,blocked);
  engine.execute(next,first.recordId,approve);assert.throws(()=>engine.execute(next,project.recordId,handover),/Copy/);
  engine.execute(next,second.recordId,approve);engine.execute(next,project.recordId,handover);engine.execute(next,project.recordId,handover);
  assert.equal(next.tasks.length,1);assert.match(next.tasks[0].text,/Atlas Collective received Next campaign v2/);
  assert.deepEqual(next.pages.filter(p=>!p.local_record),original.pages);
  const receipt=recoveryReceipt(next);assert.equal(receipt.recovered.pages,original.pages.length);assert.equal(receipt.continued_work.created_records.length,3);
  assert.ok(!receipt.recovered.source_paths.some(source=>source.startsWith('ExitForge-created/')));
  validateWorkspace(next);
});

test('invalid creation, state edits, duplicate identity and full workspace never alter input',()=>{
  const data=load(),parent=data.process.links[0].parent,stage=records.initialStates(data,'child')[0];
  const delivered=data.databases.find(db=>db.id===data.process.parent_db).rows.find(id=>data.pages.find(p=>p.id===id).properties[data.process.parent_field]==='Delivered');
  const cases=[
    ()=>records.create(data,input('child','Artwork','Approved',parent),'local-a',stamp),
    ()=>records.create(data,input('parent','Hidden bypass','Delivered'),'local-a',stamp),
    ()=>records.create(data,input('child','Artwork',stage,'missing'),'local-a',stamp),
    ()=>records.create(data,input('child','Artwork',stage,delivered),'local-a',stamp),
    ()=>records.create(data,{...input('child','Artwork',stage,parent),properties:{'Review outcome':'Approved'}},'local-a',stamp),
    ()=>records.create(data,input('parent','',records.initialStates(data,'parent')[0]),'local-a',stamp),
    ()=>records.create(data,input('parent','Next',records.initialStates(data,'parent')[0]),data.pages[0].id,stamp),
    ()=>records.edit(data,parent,{title:'Changed',body:'',properties:{'Project phase':'Delivered'}},stamp),
    ()=>records.edit(data,parent,{title:'Changed',body:'',properties:{Client:'Valid'},parent:'another'},stamp),
    ()=>records.create(data,input('parent','Next',records.initialStates(data,'parent')[0]),'local-a','yesterday')
  ];
  const before=structuredClone(data);for(const run of cases){assert.throws(run);assert.deepEqual(data,before);}
  while(data.pages.length<1000){const page=structuredClone(data.pages[0]);page.id='extra-'+data.pages.length;data.pages.push(page);}
  const full=structuredClone(data);assert.throws(()=>records.create(data,input('parent','New','In progress'),'local-new',stamp),/1,000/);assert.deepEqual(data,full);
});

test('unconfirmed processes and size overflow cannot create or edit persistent work',()=>{
  const data=load();data.process.confirmed=false;
  assert.throws(()=>records.create(data,input('parent','Next','In progress'),'local-a',stamp),/Confirm/);
  const next=load(),before=structuredClone(next);next.pages[0].body='x'.repeat(12*1024*1024-5000);
  const unchanged=structuredClone(next);
  assert.throws(()=>records.create(next,{...input('parent','Overflow','In progress'),body:'y'.repeat(15000)},'local-overflow',stamp),/size/);
  assert.deepEqual(next,unchanged);assert.equal(before.process.confirmed,true);
});

test('automatic resume allows added local links and rejects changed original bindings or action policy',()=>{
  const original=load(),parent=original.process.links[0].parent;
  const created=records.create(original,input('child','New draft','Draft',parent),'local-new',stamp).workspace;
  assert.equal(records.canResume(original,created),true);
  const edits=records.edit(created,parent,{title:'Updated project',properties:{Client:'New client'},body:'Edited'},stamp).workspace;
  assert.equal(records.canResume(original,edits),true);
  for(const mutate of [
    p=>p.process.parent_revision='',
    p=>p.process.parent_states.push('Unexpected'),
    p=>p.process.actions.find(a=>a.kind==='handover_parent').task='',
    p=>p.pages[0].source='different-source.md',
    p=>{const link=p.process.links[0],other=p.process.links.find(l=>l.parent!==link.parent).parent;link.parent=other;p.pages.find(x=>x.id===link.child).relations.push({target:other,field:'User link',confirmed:true});},
    p=>{delete p.pages.find(x=>x.id==='local-new').local_record;}
  ]){const changed=structuredClone(created);mutate(changed);assert.equal(records.canResume(original,changed),false);}
  assert.equal(records.canResume(original,{...created,id:'another'}),false);
});
