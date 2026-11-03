const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const engine=require('../static/process.js');
const load=(domain='delivery')=>JSON.parse(fs.readFileSync(path.join(__dirname,'fixtures/process-'+domain+'.json'),'utf8'));

for(const domain of ['delivery','editorial'])test(domain+': linked approval, revision and handover preserve unrelated projects',()=>{
  const data=load(domain),p=data.process,parent=p.links[0].parent,child=p.links[0].child;
  const approve=p.actions.find(a=>a.kind==='approve_child'),revise=p.actions.find(a=>a.kind==='request_changes'),handover=p.actions.find(a=>a.kind==='handover_parent');
  const untouched=structuredClone(data.pages.filter(x=>![parent,child].includes(x.id)));
  const before=structuredClone(data);assert.throws(()=>engine.execute(data,parent,handover.id),/blocked/);assert.deepEqual(data,before);
  engine.execute(data,child,revise.id);assert.equal(data.pages.find(x=>x.id===parent).properties[p.parent_field],p.parent_revision);
  assert.deepEqual(data.pages.filter(x=>![parent,child].includes(x.id)),untouched);
  engine.execute(data,child,approve.id);engine.execute(data,parent,handover.id);
  assert.equal(data.pages.find(x=>x.id===parent).properties[p.parent_field],handover.to);assert.equal(data.tasks.length,1);
  assert.match(data.tasks[0].text,/Northstar Studio/);const activity=data.activity.length;
  engine.execute(data,parent,handover.id);assert.equal(data.tasks.length,1);assert.equal(data.activity.length,activity);
  assert.equal(engine.validate(data),p,'Valid original stages remain valid after state changes');
});

test('unconfirmed rules, wrong entity actions and empty relation sets cannot mutate state',()=>{
  const data=load(),p=data.process;const before=structuredClone(data);p.confirmed=false;
  assert.throws(()=>engine.execute(data,p.links[0].child,'approve'),/confirm/);p.confirmed=true;assert.deepEqual(data,before);
  assert.throws(()=>engine.execute(data,p.links[0].parent,'approve'),/wrong entity/);
  const fresh=structuredClone(data.pages.find(x=>x.id===p.links[0].parent));fresh.id='empty-parent';fresh.title='Empty parent';data.pages.push(fresh);data.databases.find(d=>d.id===p.parent_db).rows.push(fresh.id);
  const original=structuredClone(data);assert.throws(()=>engine.execute(data,fresh.id,'handover'),/No linked items/);assert.deepEqual(data,original);
});

test('unknown code, cross-boundary links and unreusable confirmed tasks are rejected',()=>{
  for(const change of [d=>d.process.actions[0].kind='eval',d=>d.process.links[0].parent='missing',d=>d.process.actions[2].task='Northstar only',d=>d.process.parent_revision='Delivered']){
    const data=load();change(data);assert.throws(()=>engine.validate(data),/Invalid linked process/);
  }
  const data=load();data.process.confirmed=false;data.process.parent_revision=null;data.process.actions[2].task='Confirm {Client} received {Name}.';
  engine.validate(data);assert.match(engine.taskIssue(data),/\{project\}/);
});

test('keep-parent policy is explicit and receipt interpolation never expands inserted placeholders',()=>{
  const data=load(),p=data.process;p.parent_revision='';const parent=data.pages.find(x=>x.id===p.links[0].parent);
  const initial=parent.properties[p.parent_field];engine.execute(data,p.links[0].child,'revise');assert.equal(parent.properties[p.parent_field],initial);
  parent.title='Brand {client}';engine.execute(data,p.links[0].child,'approve');engine.execute(data,parent.id,'handover');
  assert.equal(data.tasks[0].text,'Confirm Northstar Studio received Brand {client}.');
});
