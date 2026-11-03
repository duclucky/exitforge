/* Work in the reconstructed application; the same controller runs offline. */
(function(global){
  'use strict';
  function mount(root,original,options={}){
    const {escape:e,icon,download,filename}=global.ExitForge,engine=global.ExitForgeProcess,{validateWorkspace,recoveryReceipt}=global.ExitForgeWorkspace;
    validateWorkspace(original);let data=structuredClone(original),selected=data.databases.find(d=>d.id===data.process.parent_db).rows[0],view='projects',query='',notice='',error=false;
    const key='exitforge.workspace.v1.'+data.id;
    if(options.portable){try{
      const saved=JSON.parse(localStorage.getItem(key));
      if(saved){if(!global.ExitForgeProcessRecords.canResume(data,saved))throw new Error();data=saved;}
    }catch(_){notice='Saved data uses different rules or cannot be read. The packaged snapshot is open; keep a backup before closing.';error=true;}}
    const pages=()=>new Map(data.pages.map(p=>[p.id,p]));
    const parents=()=>data.databases.find(d=>d.id===data.process.parent_db).rows.map(id=>pages().get(id));
    const action=kind=>data.process.actions.find(a=>a.kind===kind);
    function save(){
      if(options.portable){try{localStorage.setItem(key,JSON.stringify(data));}catch(_){notice='Changes are in memory only. Browser storage is unavailable; download a backup now.';error=true;}}
      options.onChange?.(structuredClone(data));
    }
    function message(text,bad=false){notice=text;error=bad;}
    function projectPane(){
      const p=data.process,items=parents().filter(x=>(x.title+' '+Object.values(x.properties).join(' ')).toLowerCase().includes(query.toLowerCase()));
      const current=parents().find(x=>x.id===selected)||parents()[0];
      const linked=engine.related(data,current.id),reasons=engine.blockers(data,current.id);
      const handedOver=current.properties[p.parent_field]===action('handover_parent').to&&!reasons.length;
      return `<div class="process-layout"><aside class="process-projects" aria-label="Recovered projects"><label class="field">Find a project or client<input type="search" value="${e(query)}" data-process-search></label>${items.map(page=>`<button class="process-project ${page.id===current.id?'selected':''}" data-select-project="${e(page.id)}"><small>${e(page.properties.Client||page.properties.Customer||'Source project')}</small><strong>${e(page.title)}</strong><span>${e(page.properties[p.parent_field])} · ${engine.related(data,page.id).filter(x=>x.properties[p.child_field]===action('handover_parent').approved_state).length}/${engine.related(data,page.id).length} approved</span></button>`).join('')||'<p>No matching projects. Clear the search to return.</p>'}</aside>
        <section class="process-detail" aria-label="Linked project"><div class="process-detail-heading"><div><span class="eyebrow">${e(data.databases.find(d=>d.id===p.parent_db).title)}${current.local_record?' · CREATED HERE':''}</span><h2>${e(current.title)}</h2><p>${e(current.properties.Client||current.properties.Customer||'')} · ${e(current.properties[p.parent_field])}</p></div><div class="button-row"><button class="button small" data-client-handoff="${e(current.id)}">Client handoff</button><button class="button small" data-edit-record="${e(current.id)}">Edit project</button><button class="button small" data-source="${e(current.id)}">Inspect source</button></div></div>
        <div class="process-readiness ${reasons.length?'blocked':'ready'}" id="process-readiness"><strong>${reasons.length?'Hand over blocked':handedOver?'Handed over':'Ready to hand over'}</strong><p>${reasons.length?reasons.map(e).join(' '):handedOver?'All linked items are approved. This project has been handed over.':'Every linked item satisfies the reviewed approval rule.'}</p></div>
        <div class="linked-items">${linked.map(item=>`<article class="linked-item" data-item="${e(item.id)}"><div><span class="eyebrow">${e(item.properties[p.child_field])}${item.local_record?' · CREATED HERE':''}</span><h3>${e(item.title)}</h3><div class="button-row"><button class="text-link" data-source="${e(item.id)}">Source record ${icon('arrow')}</button><button class="text-link" data-edit-record="${e(item.id)}">Edit item</button></div></div><div class="button-row"><button class="button small" data-process-action="${e(action('approve_child').id)}" data-target="${e(item.id)}">Mark ${e(action('approve_child').to)}</button><button class="button small" data-process-action="${e(action('request_changes').id)}" data-target="${e(item.id)}">Request changes</button></div></article>`).join('')}</div>
        <div class="process-add-item"><button class="button small" data-new-item="${e(current.id)}" ${!p.confirmed||current.properties[p.parent_field]===action('handover_parent').to?'disabled':''}>Add item ${icon('plus')}</button><p>${current.properties[p.parent_field]===action('handover_parent').to?'Already handed over. Request changes on an item to reopen under your reviewed policy, or create a new project.':'New items use the same linked approval rule. Empty projects cannot be handed over.'}</p></div>
        <div class="process-handover"><div><strong>A reviewed action, with real effects.</strong><p>${p.parent_revision?'A change request moves only its linked project to '+e(p.parent_revision)+'.':'You chose to keep the parent stage when changes are requested.'} No external delivery is sent.</p></div><button class="button primary" data-process-action="${e(action('handover_parent').id)}" data-target="${e(current.id)}" aria-describedby="process-readiness">Hand over ${icon('arrow')}</button></div></section></div>`;
    }
    function otherPane(){
      if(view==='sources')return `<div class="document-grid">${data.pages.map(p=>`<button class="document-card" data-source="${e(p.id)}">${icon('file')}<span><strong>${e(p.title)}</strong><small>${p.local_record?'Created here · ':'Imported source · '}${e(p.source)}</small></span></button>`).join('')}</div>`;
      if(view==='tasks')return `<div class="task-list">${data.tasks.map(t=>`<label class="task-row"><input type="checkbox" data-process-task="${e(t.id)}" ${t.done?'checked':''}><span><strong>${e(t.text)}</strong><small>${e(pages().get(t.page)?.title||'')}</small></span></label>`).join('')||'<p>No receipt tasks yet. Complete a reviewed handover to create one.</p>'}</div>`;
      return `<div class="activity-list">${data.activity.map(a=>`<div class="activity-row"><span>${e(a.text)}</span><time>${e(new Date(a.at).toLocaleString())}</time></div>`).join('')||'<p>No local changes yet.</p>'}</div>`;
    }
    function render(){
      const p=data.process,complete=parents().filter(x=>x.properties[p.parent_field]===action('handover_parent').to&&!engine.blockers(data,x.id).length).length;
      root.innerHTML=`<div class="workspace linked-workspace"><header class="workspace-header"><div><span class="eyebrow">${options.portable?'YOUR INDEPENDENT PROCESS':'RECONSTRUCTED LINKED PROCESS'}</span><h2>${e(data.name)}</h2><p>Reviewed actions. ${parents().length} projects · ${p.links.length} linked items${data.pages.some(page=>page.local_record)?' · '+data.pages.filter(page=>page.local_record).length+' records created here':''}.</p></div><div class="workspace-tools"><span class="pill local">${icon('check')} Works offline</span>${options.portable?'<button class="button small" data-process-backup>Data backup</button><button class="button small" data-process-export>Application</button><label class="button small">Restore backup<input type="file" accept=".json" data-process-restore hidden></label>':''}<button class="button small" data-process-receipt>Recovery receipt</button></div></header>
        <div class="process-route" aria-label="Reconstructed action graph"><span>Review an item</span>${icon('arrow')}<span>Approve / request changes</span>${icon('arrow')}<span>Check all linked items</span>${icon('arrow')}<strong>Hand over</strong></div>
        <div class="workspace-overview"><div><span class="mini-label">PROJECTS</span><strong>${parents().length}</strong></div><div><span class="mini-label">HANDOVERS COMPLETE</span><strong>${complete}</strong></div><div><span class="mini-label">LOCAL RECEIPTS</span><strong>${data.tasks.length}</strong></div><div class="rule-summary"><span class="mini-label">EXECUTION</span><span>${p.confirmed?'Explicitly reviewed · no AI needed to run':'Not confirmed · actions blocked'}</span></div></div>
        <div class="process-navigation"><nav class="view-tabs process-tabs" aria-label="Process views">${[['projects','Projects'],['sources','Sources'],['tasks','Follow-ups'],['activity','Activity']].map(([id,label])=>`<button class="view-tab ${view===id?'active':''}" data-process-view="${id}" aria-current="${view===id?'page':'false'}">${label}</button>`).join('')}</nav><button class="button primary small" data-new-project ${p.confirmed?'':'disabled'}>New project ${icon('plus')}</button></div>
        <div class="runtime-notice ${error?'error':''}" role="status" aria-live="polite" ${notice?'':'hidden'}>${e(notice)}</div><div class="workspace-content">${view==='projects'?projectPane():otherPane()}</div>
        <footer class="workspace-footer"><span>${data.provenance.sample?'Synthetic data · ':''}Original permissions and external automations are not recreated.</span><span>${options.portable?'Saved on this device · keep backups':'Draft stored in the studio'}</span></footer><dialog class="page-dialog" aria-label="Source record"></dialog></div>`;
      bind();
    }
    function openPage(id,returnFocus){
      const page=pages().get(id);if(!page)return;const dialog=root.querySelector('dialog');
      dialog.setAttribute('aria-label','Source record');
      dialog.innerHTML=`<div class="dialog-top"><span class="eyebrow">${page.local_record?'CREATED IN EXITFORGE':'IMPORTED SOURCE RECORD'}</span><button class="icon-button" data-close-source aria-label="Close source">${icon('close')}</button></div><h2>${e(page.title)}</h2><p class="source-path">${e(page.source)}</p><dl class="process-properties">${Object.entries(page.properties).map(([k,v])=>`<div><dt>${e(k)}</dt><dd>${e(v)}</dd></div>`).join('')}</dl><pre class="process-source-text">${e(page.body)}</pre>${page.attachments.map(id=>`<button class="attachment" data-process-asset="${e(id)}">${icon('download')}${e(data.assets[id].name)}</button>`).join('')}<label class="field">Working notes<textarea data-process-notes rows="6" maxlength="20000">${e(page.body)}</textarea></label><p class="record-error" role="alert" hidden></p><button class="button primary small" data-save-process-notes>Save notes</button>`;
      dialog.showModal();dialog.querySelector('[data-close-source]').onclick=()=>dialog.close();dialog.onclose=()=>returnFocus?.focus();
      dialog.querySelector('[data-save-process-notes]').onclick=()=>{
        try{
          const body=dialog.querySelector('textarea').value;if(body.length>20000)throw new Error('Keep working notes within 20,000 characters.');
          const next=structuredClone(data);next.pages.find(p=>p.id===id).body=body;validateWorkspace(next);data=next;
          save();dialog.close();message('Working notes saved.');render();
        }catch(error){const alert=dialog.querySelector('[role=alert]');alert.hidden=false;alert.textContent=error.message;}
      };
      dialog.querySelectorAll('[data-process-asset]').forEach(b=>b.onclick=()=>{const a=data.assets[b.dataset.processAsset];download(new Blob([Uint8Array.from(atob(a.data),c=>c.charCodeAt(0))],{type:a.mime}),a.name);});
    }
    function bind(){
      root.querySelector('[data-client-handoff]')?.addEventListener('click',event=>{
        try{global.ExitForgeHandoffView.open(root.querySelector('dialog'),()=>structuredClone(data),event.currentTarget.dataset.clientHandoff,event.currentTarget);}
        catch(error){message(error.message,true);render();}
      });
      root.querySelector('[data-new-project]').onclick=event=>openRecord({role:'parent',returnFocus:event.currentTarget});
      root.querySelector('[data-new-item]')?.addEventListener('click',event=>openRecord({role:'child',parent:event.currentTarget.dataset.newItem,returnFocus:event.currentTarget}));
      root.querySelectorAll('[data-edit-record]').forEach(button=>button.onclick=()=>openRecord({id:button.dataset.editRecord,returnFocus:button}));
      root.querySelectorAll('[data-process-view]').forEach(b=>b.onclick=()=>{view=b.dataset.processView;render();Array.from(root.querySelectorAll('[data-process-view]')).find(item=>item.dataset.processView===view)?.focus();});
      root.querySelectorAll('[data-select-project]').forEach(b=>b.onclick=()=>{selected=b.dataset.selectProject;render();root.querySelector('.process-detail h2').setAttribute('tabindex','-1');root.querySelector('.process-detail h2').focus();});
      root.querySelector('[data-process-search]')?.addEventListener('input',event=>{query=event.target.value;const position=event.target.selectionStart;render();const input=root.querySelector('[data-process-search]');input.focus();try{input.setSelectionRange(position,position);}catch(_){/* Search inputs can omit selection APIs. */}});
      root.querySelectorAll('[data-process-action]').forEach(b=>b.onclick=()=>{
        const target=b.dataset.target,id=b.dataset.processAction;
        try{const outcome=engine.execute(data,b.dataset.target,b.dataset.processAction);message(outcome.message);save();}
        catch(error){message(error.message,true);}render();Array.from(root.querySelectorAll('[data-process-action]')).find(item=>item.dataset.target===target&&item.dataset.processAction===id)?.focus();
      });
      root.querySelectorAll('[data-source]').forEach(b=>b.onclick=()=>openPage(b.dataset.source,b));
      root.querySelectorAll('[data-process-task]').forEach(input=>input.onchange=()=>{data.tasks.find(t=>t.id===input.dataset.processTask).done=input.checked;save();});
      root.querySelector('[data-process-receipt]').onclick=()=>download(new Blob([JSON.stringify(recoveryReceipt(data),null,2)],{type:'application/json'}),filename(data.name)+'-recovery-receipt.json');
      root.querySelector('[data-process-backup]')?.addEventListener('click',()=>download(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}),filename(data.name)+'.json'));
      root.querySelector('[data-process-export]')?.addEventListener('click',()=>{const doc=document.documentElement.cloneNode(true);doc.querySelector('#workspace-data').textContent=JSON.stringify(data).replace(/</g,'\\u003c').replace(/>/g,'\\u003e').replace(/&/g,'\\u0026');doc.querySelector('#workspace-main').innerHTML='';download(new Blob(['<!doctype html>\n'+doc.outerHTML],{type:'text/html'}),filename(data.name)+'.html');});
      root.querySelector('[data-process-restore]')?.addEventListener('change',async event=>{
        try{const file=event.target.files[0];if(!file||file.size>12*1024*1024)throw new Error('Choose a matching JSON backup up to 12 MB.');const next=JSON.parse(await file.text());validateWorkspace(next,data.id);if(!next.process)throw new Error('Choose a linked-process backup.');data=next;message('Workspace restored from the selected backup.');save();render();}
        catch(error){message(error.message,true);render();}
      });
    }
    function openRecord(settings){
      try{global.ExitForgeProcessRecordForm.open(root.querySelector('dialog'),data,{...settings,onCommit:(result,role,editing)=>{
        data=result.workspace;view='projects';query='';
        selected=role==='parent'?result.recordId:data.process.links.find(link=>link.child===result.recordId).parent;
        message(result.unchanged?'No record changes.':editing?'Record updated. Workflow state and relationship kept.':'Created locally. Your original export and Meta proposal are unchanged.');
        save();render();const heading=root.querySelector('.process-detail h2');heading.setAttribute('tabindex','-1');heading.focus();
      }});}catch(error){message(error.message,true);render();}
    }
    render();return {getWorkspace:()=>structuredClone(data),setWorkspace:next=>{validateWorkspace(next,data.id);data=structuredClone(next);render();},openPage};
  }
  global.ExitForgeProcessUI={mount};
})(window);
