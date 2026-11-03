const test = require('node:test');
const assert = require('node:assert/strict');
const {validateWorkspace, boardGroups, DraftStore} = require('../static/workspace.js');

test('invalid local origin cannot relabel an imported record as application-created',()=>{
  const data=project();data.pages[0].local_record={created_at:'yesterday'};
  assert.throws(()=>validateWorkspace(data),/local record/);
});

function project() {
  return {schema_version:1,id:'workspace-a',name:'Independent work',
    pages:[{id:'a',title:'Launch',source:'launch.md',body:'# Launch',properties:{Status:'Review'},links:[],relations:[],attachments:[],checklist:[]}],
    databases:[{id:'projects',title:'Projects',fields:['Status'],rows:['a']}],assets:{},
    workflow:{field:'Status',states:['Review','Delivered'],delivery_state:'Delivered',require_checklist:true,followup:'Check delivery',confirmed:true},
    tasks:[],activity:[],warnings:[],provenance:{sample:true}};
}
function storage() {
  const values = new Map();
  return {getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,value),removeItem:key=>values.delete(key)};
}
test('a valid backup retains its records and a different workspace cannot replace it',()=>{
  const data=project();assert.equal(validateWorkspace(data),data);
  assert.throws(()=>validateWorkspace(data,'workspace-b'),/workspace/i);
});
test('malformed references, duplicate pages and broken collections are rejected',()=>{
  const variants=[data=>data.pages.push(structuredClone(data.pages[0])),data=>data.databases[0].rows.push('missing'),
    data=>data.tasks.push({id:'task',page:'missing',text:'Bad reference',done:false}),data=>data.pages[0].links=null,
    data=>data.provenance=null,data=>data.workflow.states=Array(9).fill('Stage')];
  for(const alter of variants){const data=project();alter(data);assert.throws(()=>validateWorkspace(data));}
});
test('executable attachments, invalid base64 and unsafe filenames cannot enter a portable workspace',()=>{
  for(const asset of [{name:'attack.html',mime:'text/html',data:'PHNjcmlwdD4='},
    {name:'notes.txt',mime:'text/plain',data:'%%%not-base64'},
    {name:'../notes.txt',mime:'text/plain',data:'eA=='},
    {name:'C:\\notes.txt',mime:'text/plain',data:'eA=='}]){
    const data=project();data.assets.file=asset;data.pages[0].attachments=['file'];
    assert.throws(()=>validateWorkspace(data));
  }
});
test('safe attachments and untrusted text remain usable as data',()=>{
  const data=project();data.pages[0].body='<script>window.BAD=true</script>';
  data.assets.file={name:'notes.txt',mime:'text/plain',data:'eA=='};data.pages[0].attachments=['file'];
  assert.equal(validateWorkspace(data).pages[0].body,data.pages[0].body);
});
test('draft resumes actual edits and stage without retaining cloud consent',()=>{
  const store=new DraftStore(storage()),data=project();data.pages[0].body='Actual saved edit';
  assert.equal(store.save({project:data,step:2,cloudConsent:true}).ok,true);
  const result=store.load();assert.equal(result.error,'');assert.equal(result.draft.project.pages[0].body,'Actual saved edit');
  assert.equal(result.draft.step,2);assert.equal(Object.hasOwn(result.draft,'cloudConsent'),false);
});
test('unfinished workflow review survives as a draft without approving the rule',()=>{
  const store=new DraftStore(storage()),data=project();data.workflow.confirmed=false;
  assert.equal(store.save({project:data,step:1,review:{name:'My new name',field:'Status',states:'Review, Delivered',delivery:'Delivered',followup:'My follow-up',requireChecklist:true,acceptRelations:false}}).ok,true);
  const draft=store.load().draft;assert.equal(draft.review.name,'My new name');assert.equal(draft.project.workflow.confirmed,false);
});
test('quota failure preserves the previous draft and surfaces the need for a backup',()=>{
  const backend=storage(),store=new DraftStore(backend);assert.equal(store.save({project:project(),step:1}).ok,true);
  backend.setItem=()=>{throw new Error('QuotaExceededError');};
  const changed=project();changed.name='Unsaved change';assert.equal(store.save({project:changed,step:2}).ok,false);
  assert.equal(store.load().draft.project.name,'Independent work');
});
test('corrupt drafts fail safely and explicit removal affects only the studio draft',()=>{
  const backend=storage(),store=new DraftStore(backend);backend.setItem('unrelated','keep');
  store.save({project:project(),step:2});assert.equal(store.clear().ok,true);
  assert.equal(store.load().draft,null);assert.equal(backend.getItem('unrelated'),'keep');
  backend.getItem=()=>'{broken';const result=store.load();assert.equal(result.draft,null);assert.ok(result.error);
});
test('database grouping keeps unknown and unassigned values visible exactly once',()=>{
  const data=project();data.pages.push({...structuredClone(data.pages[0]),id:'b',properties:{Status:'Archived'}});
  data.pages.push({...structuredClone(data.pages[0]),id:'c',properties:{}});data.databases[0].rows.push('b','c');
  const groups=boardGroups(data,data.pages);const ids=groups.flatMap(group=>group.pages.map(page=>page.id));
  assert.deepEqual(ids.sort(),['a','b','c']);assert.equal(new Set(ids).size,3);
});
test('a workspace without a workflow renders every record once',()=>{
  const data=project();data.workflow.field='';const groups=boardGroups(data,data.pages);
  assert.equal(groups.length,1);assert.equal(groups[0].pages.length,1);
});

test('recovery receipt separates original AI proposal from approved corrections without changing data',()=>{
  const {recoveryReceipt}=require('../static/workspace.js');
  const data=project();data.provenance.sample=true;
  data.ai_review={specification:{followup:'Northstar only',unknowns:['Permissions absent'],rationale:'A proposal'},calls:[{provider:'Baseten',elapsed_ms:12}]};
  data.workflow.followup='Confirm {client} received {project}.';
  const original=structuredClone(data),receipt=recoveryReceipt(data);
  assert.equal(receipt.sample,true);assert.equal(receipt.recovered.pages,1);
  assert.equal(receipt.meta_proposal.specification.followup,'Northstar only');
  assert.equal(receipt.workflow.followup,'Confirm {client} received {project}.');
  receipt.workflow.followup='changed';receipt.meta_proposal.specification.followup='changed';
  assert.deepEqual(data,original);
  assert.ok(receipt.limits.some(x=>x.includes('not been measured')));
});
