const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const pack=require('../static/handoff.js');
const load=(domain='delivery')=>JSON.parse(fs.readFileSync(path.join(__dirname,'fixtures/process-'+domain+'.json'),'utf8'));
const stamp='2026-11-02T12:00:00.000Z';
function ready(domain){const data=load(domain),p=data.process,id=p.links[0].parent;data.pages.find(x=>x.id===id).properties[p.parent_field]=p.actions.find(a=>a.kind==='handover_parent').to;p.links.filter(l=>l.parent===id).forEach(l=>data.pages.find(x=>x.id===l.child).properties[p.child_field]=p.actions.find(a=>a.kind==='approve_child').to);return {data,id};}

test('editorial handoff uses its actual bindings and state names',()=>{
  const {data,id}=ready('editorial'),result=pack.build(data,id,{},stamp);
  assert.equal(result.records.project.state,'Released');assert.ok(result.records.items.every(item=>item.state==='Accepted'));
  assert.equal(result.records.project.title,'Autumn issue');assert.equal(result.manifest.included.items,2);
});

test('project projection excludes other clients, source paths, AI review and unselected notes/files',()=>{
  const {data,id}=ready(),before=structuredClone(data);const parent=data.pages.find(p=>p.id===id);parent.body='PRIVATE WORKING NOTES';
  parent.properties.Email='INTERNAL PRIVATE EMAIL';
  const other=data.pages.find(p=>p.properties.Client==='Cedar & Co');other.body='OTHER CLIENT SECRET';
  data.assets['other-secret']={name:'private.txt',mime:'text/plain',data:btoa('OTHER ASSET SECRET')};other.attachments.push('other-secret');
  const input=structuredClone(data),result=pack.build(data,id,{},stamp);assert.deepEqual(data,input);
  const output=JSON.stringify([result.manifest,result.records]);
  for(const secret of ['Cedar & Co','OTHER CLIENT SECRET','OTHER ASSET SECRET','PRIVATE WORKING NOTES','INTERNAL PRIVATE EMAIL','process_review','cloud_calls','source'])assert.ok(!output.includes(secret),secret);
  assert.equal(result.records.items.length,2);assert.equal(result.records.files.length,0);assert.equal(result.manifest.included.notes,false);
  assert.throws(()=>pack.build(data,id,{assetIds:['other-secret']},stamp),/outside/);
  assert.equal(before.pages.length,data.pages.length);
});

test('eligibility requires confirmation, related approval and the completed handover stage',()=>{
  const {data,id}=ready(),before=structuredClone(data),p=data.process;
  data.pages.find(x=>x.id===id).properties[p.parent_field]='In progress';assert.match(pack.preview(data,id).reasons.join(' '),/Hand over this project first/);assert.throws(()=>pack.build(data,id),/blocked/);
  data.pages.find(x=>x.id===id).properties[p.parent_field]='Delivered';data.pages.find(x=>x.id===p.links.find(l=>l.parent===id).child).properties[p.child_field]='Draft';
  assert.throws(()=>pack.build(data,id),/must be Approved/);
  const unconfirmed=structuredClone(before);unconfirmed.process.confirmed=false;assert.throws(()=>pack.build(unconfirmed,id),/Confirm/);
  assert.throws(()=>pack.preview(before,'missing'),/Choose a project/);
});

test('notes and project-bound files require explicit selection, with bounded settings',()=>{
  const {data,id}=ready(),view=pack.preview(data,id),assetId=view.available[0].id;
  const result=pack.build(data,id,{includeNotes:true,assetIds:[assetId]},stamp);
  assert.equal(result.manifest.included.attachments,1);assert.equal(result.records.project.notes,data.pages.find(p=>p.id===id).body);
  assert.match(result.records.files[0].path,/^files\/001-/);
  for(const settings of [{includeNotes:'yes'},{assetIds:[assetId,assetId]},{assetIds:'all'},{assetIds:['unknown']},{includeHistory:true}])assert.throws(()=>pack.build(data,id,settings,stamp));
  const original=structuredClone(data);assert.throws(()=>pack.build(data,id,{},'yesterday'),/snapshot time/);assert.deepEqual(data,original);
});

test('oversized opted-in notes stop without changing input',()=>{
  const {data,id}=ready();data.pages.find(p=>p.id===id).body='x'.repeat(9*1024*1024);const original=structuredClone(data);
  assert.throws(()=>pack.build(data,id,{includeNotes:true},stamp),/16 MB/);assert.deepEqual(data,original);
  assert.equal(pack.build(data,id,{},stamp).manifest.included.notes,false);
});
