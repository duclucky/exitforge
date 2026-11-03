const test = require('node:test');
const assert = require('node:assert/strict');
const {transition} = require('../static/runtime.js');

function project() {
  return {workflow:{field:'Status',states:['Review','Delivered'],delivery_state:'Delivered',confirmed:true,require_checklist:true,followup:'Check the delivery'},pages:[{id:'a',title:'Launch',properties:{Status:'Review'},checklist:[{text:'Approval',done:false}]}],tasks:[],activity:[]};
}
test('incomplete checklist blocks delivery and does not change data',()=>{
  const data=project(); assert.throws(()=>transition(data,'a','Delivered'),/checklist/i);
  assert.equal(data.pages[0].properties.Status,'Review'); assert.equal(data.tasks.length,0);
});
test('approved delivery persists status and creates one follow-up across retries',()=>{
  const data=project();data.pages[0].checklist[0].done=true;
  transition(data,'a','Delivered');transition(data,'a','Review');transition(data,'a','Delivered');
  assert.equal(data.pages[0].properties.Status,'Delivered');assert.equal(data.tasks.length,1);
  assert.equal(data.tasks[0].page,'a');
});
test('unconfirmed inferred rules never execute an automation',()=>{
  const data=project();data.workflow.confirmed=false;
  transition(data,'a','Delivered');assert.equal(data.tasks.length,0);
});
test('unknown states are rejected instead of invented',()=>{
  assert.throws(()=>transition(project(),'a','Delete everything'),/state/i);
});

test('a shared follow-up template resolves the actual project and client independently',()=>{
  const data=project();
  data.workflow.followup='Confirm {client} received {project}.';
  data.pages[0].properties.Client='Northstar Studio';
  data.pages[0].checklist[0].done=true;
  data.pages.push({id:'b',title:'Website refresh',properties:{Status:'Review',Customer:'Cedar & Co'},checklist:[]});
  transition(data,'a','Delivered');transition(data,'b','Delivered');
  assert.equal(data.tasks.find(t=>t.page==='a').text,'Confirm Northstar Studio received Launch.');
  assert.equal(data.tasks.find(t=>t.page==='b').text,'Confirm Cedar & Co received Website refresh.');
  transition(data,'b','Review');transition(data,'b','Delivered');
  assert.equal(data.tasks.length,2);
});

test('follow-up interpolation has a missing-client fallback and does not interpret inserted text',()=>{
  const data=project();data.pages[0].checklist[0].done=true;
  data.pages[0].title='A {client} <script> note';
  data.workflow.followup='Confirm {client} received {project}. Keep {custom} literal.';
  transition(data,'a','Delivered');
  assert.equal(data.tasks[0].text,'Confirm the client received A {client} <script> note. Keep {custom} literal.');
});

test('an AI global rule cannot create another client task with recorded Northstar wording',()=>{
  const data=project();
  data.ai_review={specification:{followup:'Keep a local receipt-check task for Northstar handoff'}};
  data.workflow.followup=data.ai_review.specification.followup;
  data.pages[0].properties.Client='Northstar Studio';data.pages[0].checklist[0].done=true;
  data.pages.push({id:'b',title:'Website refresh',properties:{Status:'Review',Client:'Cedar & Co'},checklist:[]});
  const original=structuredClone(data);
  assert.throws(()=>transition(data,'b','Delivered'),/reusable|\{client\}|\{project\}/i);
  assert.deepEqual(data,original,'A rejected AI rule must not mutate project state or tasks');
  data.workflow.followup='Confirm {client} received {project}.';
  transition(data,'b','Delivered');
  assert.equal(data.tasks[0].text,'Confirm Cedar & Co received Website refresh.');
  assert.equal(data.ai_review.specification.followup,original.ai_review.specification.followup);
});

test('a single-record AI rule and manual literal rules retain their custom wording',()=>{
  const data=project();data.pages[0].checklist[0].done=true;
  data.ai_review={specification:{followup:'Check the delivery'}};
  transition(data,'a','Delivered');assert.equal(data.tasks[0].text,'Check the delivery');
  delete data.ai_review;data.pages.push({id:'b',title:'Second job',properties:{Status:'Review'},checklist:[]});
  transition(data,'b','Delivered');assert.equal(data.tasks[0].text,'Check the delivery');
});

test('legacy status changes cannot bypass approval of linked deliverables',()=>{
  const fs=require('node:fs'),path=require('node:path');
  const data=JSON.parse(fs.readFileSync(path.join(__dirname,'fixtures/process-delivery.json'),'utf8'));
  const process=data.process;
  data.workflow={field:process.parent_field,states:process.parent_states,delivery_state:'Delivered',confirmed:true,require_checklist:false,followup:''};
  const original=structuredClone(data);
  assert.throws(()=>transition(data,process.links[0].parent,'Delivered'),/related|process|approved/i);
  assert.deepEqual(data,original);
});
