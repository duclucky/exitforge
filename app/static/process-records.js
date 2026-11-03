/* Transactional local work creation. Reviewed process rules stay unchanged. */
(function(global){
  'use strict';
  const metadata=['Client','Customer','Owner','Assignee','Priority','Due','Due date'];
  const workspace=()=>typeof module!=='undefined'&&module.exports?require('./workspace.js'):global.ExitForgeWorkspace;
  function check(ok,message){if(!ok)throw new Error(message);}
  function binding(data,role){
    check(['parent','child'].includes(role),'Choose a project or linked item.');
    const p=data.process;check(p?.confirmed===true,'Confirm the process before creating or editing work.');
    return data.databases.find(db=>db.id===p[role+'_db']);
  }
  function fields(data,role){return binding(data,role).fields.filter(field=>metadata.includes(field)&&field!==data.process[role+'_field']);}
  function initialStates(data,role){
    binding(data,role);const p=data.process;
    const terminal=p.actions.find(a=>a.kind===(role==='parent'?'handover_parent':'approve_child')).to;
    return p[role+'_states'].filter(state=>state!==terminal);
  }
  function content(data,role,input){
    check(typeof input.title==='string'&&input.title.trim().length>0&&input.title.trim().length<=160,'Enter a record name between 1 and 160 characters.');
    check(typeof input.body==='string'&&input.body.length<=20000,'Keep working notes within 20,000 characters.');
    const values=input.properties;
    check(values!==null&&typeof values==='object'&&!Array.isArray(values),'Record fields must be text values.');
    const allowed=fields(data,role);
    check(Object.entries(values).every(([field,value])=>allowed.includes(field)&&typeof value==='string'&&value.length<=500),'Edit only the supported record fields. Use process actions for status and keep relationships unchanged.');
  }
  function commit(next,record,operation,at){
    check(typeof at==='string'&&Number.isFinite(Date.parse(at))&&new Date(at).toISOString()===at,'A valid creation or edit time is required.');
    next.activity.unshift({at,page:record.id,operation,text:(operation==='create_record'?'Created locally':'Edited record')+' · '+record.title});
    next.activity=next.activity.slice(0,100);workspace().validateWorkspace(next);
    return {workspace:next,recordId:record.id};
  }
  function create(data,input,id='local-'+global.crypto.randomUUID(),at=new Date().toISOString()){
    workspace().validateWorkspace(data);const db=binding(data,input.role);content(data,input.role,input);
    check(Object.keys(input).every(k=>['role','title','body','properties','parent','initial_state'].includes(k)),'Unsupported record creation field.');
    check(data.pages.length<1000,'This workspace has reached its 1,000-record limit.');
    check(typeof id==='string'&&id.trim()===id&&/^local-[A-Za-z0-9_-]{1,80}$/.test(id)&&!data.pages.some(p=>p.id===id),'A new unique local record identity is required.');
    check(initialStates(data,input.role).includes(input.initial_state),'Choose a non-final initial stage; use the reviewed actions to approve or hand over.');
    const next=structuredClone(data),p=next.process;
    const record={id,title:input.title.trim(),body:input.body,source:'ExitForge-created/'+id+'.md',database:db.id,
      properties:Object.fromEntries(db.fields.map(field=>[field,''])),links:[],relations:[],attachments:[],checklist:[],local_record:{created_at:at}};
    Object.assign(record.properties,input.properties);record.properties[p[input.role+'_field']]=input.initial_state;
    for(const field of ['Name','Title'])if(db.fields.includes(field)&&field!==p[input.role+'_field'])record.properties[field]=record.title;
    if(input.role==='child'){
      const parent=next.pages.find(page=>page.id===input.parent),parentDb=binding(next,'parent');
      check(parent&&parentDb.rows.includes(parent.id),'Choose an existing parent project.');
      check(parent.properties[p.parent_field]!==p.actions.find(a=>a.kind==='handover_parent').to,'This project has been handed over. Reopen it through its reviewed change-request policy, or create another project.');
      record.relations.push({field:'ExitForge parent',target:parent.id,confirmed:true});p.links.push({child:id,parent:parent.id});
    }else check(input.parent===undefined||input.parent==='','A project cannot be created as a linked item.');
    next.pages.push(record);next.databases.find(d=>d.id===db.id).rows.push(id);
    return commit(next,record,'create_record',at);
  }
  function edit(data,id,input,at=new Date().toISOString()){
    workspace().validateWorkspace(data);
    const role=['parent','child'].find(role=>binding(data,role).rows.includes(id));
    check(role,'Choose an existing process record.');content(data,role,input);
    check(Object.keys(input).every(k=>['title','body','properties'].includes(k)),'Status and relationships must be changed through reviewed process actions.');
    const next=structuredClone(data),record=next.pages.find(p=>p.id===id);
    const before=JSON.stringify([record.title,record.body,record.properties]);
    record.title=input.title.trim();record.body=input.body;Object.assign(record.properties,input.properties);
    for(const field of ['Name','Title'])if(Object.hasOwn(record.properties,field)&&field!==data.process[role+'_field'])record.properties[field]=record.title;
    if(before===JSON.stringify([record.title,record.body,record.properties]))return {workspace:next,recordId:id,unchanged:true};
    return commit(next,record,'edit_record',at);
  }
  function canResume(packaged,saved){
    try{
      workspace().validateWorkspace(packaged);workspace().validateWorkspace(saved,packaged.id);
      const policy=p=>JSON.stringify([p.version,p.parent_db,p.child_db,p.parent_field,p.child_field,p.parent_states,p.child_states,p.actions,p.parent_revision,p.confirmed]);
      if(!saved.process||policy(packaged.process)!==policy(saved.process))return false;
      const originalPages=new Map(packaged.pages.map(p=>[p.id,p])),current=new Map(saved.pages.map(p=>[p.id,p]));
      if(packaged.pages.some(p=>!current.has(p.id)||current.get(p.id).source!==p.source||JSON.stringify(current.get(p.id).local_record)!==JSON.stringify(p.local_record)))return false;
      const links=new Map(saved.process.links.map(link=>[link.child,link.parent]));
      if(packaged.process.links.some(link=>links.get(link.child)!==link.parent))return false;
      for(const role of ['parent','child']){
        const before=packaged.databases.find(db=>db.id===packaged.process[role+'_db']);
        const after=saved.databases.find(db=>db.id===before.id);
        if(JSON.stringify(before.fields)!==JSON.stringify(after.fields)||before.rows.some(id=>!after.rows.includes(id)))return false;
      }
      for(const page of saved.pages.filter(page=>!originalPages.has(page.id))){
        if(!page.local_record||!['parent','child'].some(role=>saved.databases.find(db=>db.id===saved.process[role+'_db']).rows.includes(page.id)))return false;
      }
      return saved.process.links.every(link=>originalPages.has(link.child)||current.get(link.child)?.local_record);
    }catch(_){return false;}
  }
  const api={fields,initialStates,create,edit,canResume};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else global.ExitForgeProcessRecords=api;
})(typeof window!=='undefined'?window:globalThis);
