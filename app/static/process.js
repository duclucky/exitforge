/* Typed linked-record execution. Source text is never executable code. */
(function(global){
  'use strict';
  const object=x=>x!==null&&typeof x==='object'&&!Array.isArray(x);
  const text=(x,max=160)=>typeof x==='string'&&x.length<=max;
  function check(ok,message){if(!ok)throw new Error('Invalid linked process: '+message);}
  function validate(data,p=data.process){
    check(object(p)&&p.version===1,'unsupported version.');
    const fields=['version','name','parent_db','child_db','parent_field','child_field','parent_states','child_states','links','actions','evidence_sources','unknowns'];
    check(fields.every(k=>Object.hasOwn(p,k))&&Object.keys(p).every(k=>fields.includes(k)||['confirmed','parent_revision'].includes(k)),'unsupported fields.');
    check(['name','parent_db','child_db','parent_field','child_field'].every(k=>text(p[k])),'invalid binding.');
    const databases=new Map(data.databases.map(d=>[d.id,d])),pages=new Map(data.pages.map(x=>[x.id,x]));
    const parent=databases.get(p.parent_db),child=databases.get(p.child_db);
    check(parent&&child&&parent!==child,'choose two distinct databases.');
    for(const [role,db] of [['parent',parent],['child',child]]){
      check(db.fields.includes(p[role+'_field']),'field absent from database.');
      const states=p[role+'_states'];
      check(Array.isArray(states)&&states.length>0&&states.length<=8&&states.every(s=>text(s,100)&&s)&&new Set(states).size===states.length,'invalid states.');
      check(db.rows.every(id=>pages.has(id)&&(!pages.get(id).properties[p[role+'_field']]||states.includes(pages.get(id).properties[p[role+'_field']]))),'unknown source state.');
    }
    check(Array.isArray(p.links)&&p.links.length>0&&p.links.length<=1000,'missing relations.');
    const seen=new Set();
    for(const link of p.links){
      check(object(link)&&Object.keys(link).length===2&&child.rows.includes(link.child)&&parent.rows.includes(link.parent)&&!seen.has(link.child),'invalid/duplicate relation.');
      const source=pages.get(link.child);
      check(source.links.some(l=>!l.external&&l.target===link.parent)||source.relations.some(l=>l.confirmed&&l.target===link.parent),'relation has no explicit source link.');
      seen.add(link.child);
    }
    check(child.rows.every(id=>seen.has(id)),'every child needs one parent.');
    check(Array.isArray(p.evidence_sources)&&p.evidence_sources.length>0&&p.evidence_sources.length<=40&&p.evidence_sources.every(x=>text(x,500)),'invalid citations.');
    check(Array.isArray(p.unknowns)&&p.unknowns.length<=20&&p.unknowns.every(x=>text(x,1000)),'invalid unknowns.');
    check(Array.isArray(p.actions)&&p.actions.length===3,'three supported actions required.');
    const kinds=new Set(),ids=new Set();
    for(const a of p.actions){
      check(object(a)&&['approve_child','request_changes','handover_parent'].includes(a.kind)&&!kinds.has(a.kind),'unsupported action opcode.');
      const allowed=['id','kind','label','to','evidence_sources',...(a.kind==='request_changes'?['parent_to']:a.kind==='handover_parent'?['approved_state','task']:[])];
      check(Object.keys(a).length===allowed.length&&allowed.every(k=>Object.hasOwn(a,k)),'unsupported action parameters.');
      check(text(a.id,64)&&/^[a-zA-Z][a-zA-Z0-9_-]*$/.test(a.id)&&!ids.has(a.id)&&text(a.label,80),'invalid action identity.');
      check((a.kind==='handover_parent'?p.parent_states:p.child_states).includes(a.to),'unsupported action state.');
      check(Array.isArray(a.evidence_sources)&&a.evidence_sources.length>0&&a.evidence_sources.every(s=>p.evidence_sources.includes(s)),'invalid action citations.');
      if(a.kind==='request_changes')check(p.parent_states.includes(a.parent_to)||a.parent_to==='','unsupported proposed parent revision.');
      if(a.kind==='handover_parent')check(p.child_states.includes(a.approved_state)&&text(a.task,180),'invalid guard/task.');
      ids.add(a.id);kinds.add(a.kind);
    }
    const approve=p.actions.find(a=>a.kind==='approve_child'),revise=p.actions.find(a=>a.kind==='request_changes'),handover=p.actions.find(a=>a.kind==='handover_parent');
    check(approve.to===handover.approved_state&&revise.to!==approve.to,'inconsistent approval actions.');
    check(revise.parent_to!==handover.to&&p.parent_revision!==handover.to,'a change request cannot complete its parent.');
    check(p.confirmed===undefined||typeof p.confirmed==='boolean','invalid confirmation.');
    check(p.parent_revision===undefined||p.parent_revision===null||p.parent_revision===''||p.parent_states.includes(p.parent_revision),'invalid reviewed revision stage.');
    if(p.confirmed){check(p.parent_revision!==null&&p.parent_revision!==undefined,'review the parent revision policy.');check(!taskIssue(data,p),'make the receipt task reusable.');}
    return p;
  }
  function taskIssue(data,p=data.process){
    const task=p.actions.find(a=>a.kind==='handover_parent').task;
    const parent=data.databases.find(d=>d.id===p.parent_db);
    const clients=new Set(data.pages.filter(x=>parent.rows.includes(x.id)).map(x=>x.properties.Client?.trim()||x.properties.Customer?.trim()).filter(Boolean));
    if(task&&(!task.includes('{project}')||(clients.size>1&&!task.includes('{client}'))))return 'Use {project} and {client} in a shared receipt task, or leave it empty.';
    return '';
  }
  function related(data,parentId){return data.process.links.filter(l=>l.parent===parentId).map(l=>data.pages.find(p=>p.id===l.child));}
  function blockers(data,parentId){
    const p=data.process,action=p.actions.find(a=>a.kind==='handover_parent'),items=related(data,parentId);
    if(!items.length)return ['No linked items. Hand over is blocked until the source relationship is established.'];
    return items.filter(item=>item.properties[p.child_field]!==action.approved_state).map(item=>item.title+' must be '+action.approved_state+'.');
  }
  function execute(data,pageId,actionId){
    const p=validate(data);check(p.confirmed===true,'review and confirm before running actions.');
    const action=p.actions.find(a=>a.id===actionId),page=data.pages.find(x=>x.id===pageId);
    check(action&&page,'unknown action or record.');
    const db=data.databases.find(d=>d.id===(action.kind==='handover_parent'?p.parent_db:p.child_db));
    check(db.rows.includes(pageId),'action targets the wrong entity.');
    const changes=[];let task=null;
    if(action.kind==='handover_parent'){
      const reasons=blockers(data,pageId);if(reasons.length)throw new Error('Hand over blocked: '+reasons.join(' '));
      changes.push([page,p.parent_field,action.to]);
      if(action.task&&!data.tasks.some(t=>t.id==='process-receipt:'+page.id)){
        const values={project:page.title,client:page.properties.Client?.trim()||page.properties.Customer?.trim()||'the client'};
        task={id:'process-receipt:'+page.id,page:page.id,text:action.task.replace(/\{(project|client)\}/g,(_,k)=>values[k]),done:false};
      }
    }else{
      changes.push([page,p.child_field,action.to]);
      if(action.kind==='request_changes'&&p.parent_revision){
        const link=p.links.find(l=>l.child===pageId),parent=data.pages.find(x=>x.id===link.parent);
        changes.push([parent,p.parent_field,p.parent_revision]);
      }
    }
    if(!task&&changes.every(([record,field,value])=>record.properties[field]===value))return {changed:false,message:'This action is already reflected in the workspace.'};
    // Every check precedes the first mutation; a blocked operation is atomic.
    changes.forEach(([record,field,value])=>record.properties[field]=value);
    const stamp=new Date().toISOString();if(task)data.tasks.unshift({...task,created_at:stamp});
    data.activity.unshift({at:stamp,page:page.id,text:action.kind+' · '+page.title});data.activity=data.activity.slice(0,100);
    return {changed:true,message:action.kind==='handover_parent'?'Hand over complete. '+(task?'One local receipt task created.':'Existing receipt kept.'):'Updated '+page.title+'.'+(changes.length>1?' Linked project moved to '+p.parent_revision+'.':'')};
  }
  const api={validate,execute,related,blockers,taskIssue};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else global.ExitForgeProcess=api;
})(typeof window!=='undefined'?window:globalThis);
