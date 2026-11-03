/* Review model-derived bindings and decide the policy before activation. */
(function(global){
  'use strict';
  function inputHTML(project){
    if(project.databases.length<2)return '';
    return `<details class="panel process-input"><summary>Rebuild a linked workflow with Meta</summary><p>Show the actions that connect these databases. Muse Spark Open reads your source records and ordered observations, then proposes a reviewable process.</p><label class="field">Ordered workflow screenshots<input type="file" id="process-observations" accept="image/png,image/jpeg" multiple><small>One to six PNG/JPEG files, up to 2 MB each / 8 MB total. Add them in before/action/after order. Images are kept for this operation only; retain your originals.</small></label><label class="checkbox-row"><input type="checkbox" id="process-consent"><span>Send source records and these screenshots to Meta open weights hosted by Baseten for one reconstruction request. Usage may incur charges.</span></label><button class="button primary small" id="reconstruct-process">Reconstruct linked process</button><p>Unsupported or ambiguous source relationships remain blocked. No original permissions or external automations are recreated.</p></details>`;
  }
  function bindInput(root,onRequest,toast){
    const button=root.querySelector('#reconstruct-process');if(!button)return;
    const input=root.querySelector('#process-observations'),consent=root.querySelector('#process-consent');
    input.onchange=()=>consent.checked=false;
    button.onclick=async()=>{
      if(!consent.checked){toast('Confirm the screenshot/source operation before reconstruction.',true);return;}
      const files=Array.from(input.files);if(!files.length||files.length>6){toast('Choose one to six ordered observations.',true);return;}
      if(files.some(f=>!['image/png','image/jpeg'].includes(f.type)||f.size>2*1024*1024)||files.reduce((n,f)=>n+f.size,0)>8*1024*1024){toast('Use PNG/JPEG up to 2 MB each and 8 MB total.',true);return;}
      consent.checked=false;button.disabled=true;button.textContent='Reading the workflow with Meta…';
      try{
        const observations=await Promise.all(files.map(file=>new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve({data_url:reader.result});reader.onerror=()=>reject(new Error('An observation could not be read.'));reader.readAsDataURL(file);})));
        await onRequest(observations);
      }catch(error){toast(error.message+' Your source remains available. No automatic retry was made.',true);}
      finally{button.disabled=false;button.textContent='Reconstruct linked process';}
    };
  }
  function review(root,project,options){
    const {escape:e,icon,download,filename}=global.ExitForge,engine=global.ExitForgeProcess,p=project.process;
    const lookup=new Map(project.pages.map(x=>[x.id,x]));
    const parent=project.databases.find(d=>d.id===p.parent_db),child=project.databases.find(d=>d.id===p.child_db);
    const raw=project.process_review,revise=p.actions.find(a=>a.kind==='request_changes'),handover=p.actions.find(a=>a.kind==='handover_parent');
    const steps=raw?.observations||[];
    root.innerHTML=`<div class="intro-row"><div><span class="eyebrow">DATA + OBSERVATIONS → A WORKING PROCESS</span><h1>Your workflow.<br><span class="headline-highlight">A new home.</span></h1><p>Review how the records connect. Choose the behavior that will run in your independent application.</p></div><button class="button small" id="process-review-receipt">Download recovery receipt</button></div>
      <section class="meta-decision" aria-label="Process reconstruction"><div><span class="eyebrow">${raw?.recorded?'RECORDED ACTUAL META RUN · SYNTHETIC SOURCE':'SAVED MODEL PROPOSAL · REVIEW REQUIRED'}</span><h2>${e(p.name)}</h2><p>${parent.rows.length} ${e(parent.title)} · ${child.rows.length} ${e(child.title)} · ${p.links.length} source-linked relationships. Opening this saved proposal makes no new inference request.</p></div><span class="pill">${raw?.calls?.length||0} recorded Meta operation(s)</span></section>
      ${raw?.binding_resolution?.method==='explicit_source_links'?`<section class="panel" aria-label="Source relationship coverage"><strong>${e(raw.binding_resolution.relationship_count)} relationships resolved from explicit export links.</strong><p>All items are included. Meta proposed the actions and status fields; the export supplies record relationships and observed states. Review both before activation.</p><details><summary>Original model proposal and source resolution</summary><pre class="process-source-text">${e(JSON.stringify({model_proposal:raw.model_proposal,source_resolution:raw.binding_resolution},null,2))}</pre></details></section>`:''}
      ${steps.length?`<details class="panel process-observations"><summary>What Meta observed · ${steps.length} steps</summary><p>Selected observations establish only the visible behavior. Hidden rules remain unknown.</p><div class="observation-strip">${steps.map((step,i)=>`<figure>${/^\/process-example\/(delivery|editorial)\/frame-[1-6]\.png$/.test(step.preview||'')?`<a href="${e(step.preview)}" target="_blank" rel="noopener"><img src="${e(step.preview)}" alt="Synthetic original workflow observation ${i+1}"></a>`:''}<figcaption>Step ${i+1} · ${e(step.id)}</figcaption></figure>`).join('')}</div></details>`:''}
      <div class="review-grid process-review-grid"><div><section class="panel"><div class="panel-heading"><h2>How the work connects</h2><span class="pill">SOURCE BINDINGS</span></div><p>${e(parent.title)} uses <strong>${e(p.parent_field)}</strong>. ${e(child.title)} uses <strong>${e(p.child_field)}</strong>.</p><div class="process-binding-list">${parent.rows.map(id=>`<div><strong>${e(lookup.get(id).title)}</strong><ul>${p.links.filter(l=>l.parent===id).map(l=>`<li>${e(lookup.get(l.child).title)}</li>`).join('')||'<li>No linked items: handover will be blocked.</li>'}</ul></div>`).join('')}</div></section>
      <section class="panel process-proposed-actions"><h2>Three actions Meta mapped</h2>${p.actions.map(a=>`<article><span class="eyebrow">${e(a.kind.replaceAll('_',' '))}</span><strong>${e(a.label)} → ${e(a.to)}</strong><p>${a.kind==='handover_parent'?'Only when every linked item is '+e(a.approved_state)+'.':a.kind==='request_changes'?'Observed parent change: '+e(a.parent_to||'not established')+'.':'Changes the selected item only.'}</p><small>Evidence: ${a.evidence_sources.map(e).join(', ')}</small></article>`).join('')}</section>
      <details class="panel"><summary>Missing behavior & limits (${p.unknowns.length})</summary><ul>${p.unknowns.map(x=>`<li>${e(x)}</li>`).join('')}</ul><p>Only the reviewed local actions run. No email, account permission or external delivery is reproduced.</p></details></div>
      <section class="panel process-policy"><span class="reference-tag">YOUR DECISION</span><h2>What should a change request do?</h2><p>Approve the policy explicitly, even when a source observation suggests it.</p><label class="field">Parent stage after a change request<select id="process-parent-policy"><option value="">Choose a policy…</option><option value="__keep__" ${p.parent_revision===''?'selected':''}>Keep the parent's current stage</option>${p.parent_states.filter(state=>state!==handover.to).map(state=>`<option value="${e(state)}" ${p.parent_revision===state?'selected':''}>Move parent to ${e(state)}</option>`).join('')}</select></label><p class="review-footer">Model observation: ${e(revise.parent_to||'parent-stage effect was not established')}.</p>
      <label class="field">Local receipt task<input id="process-task-template" maxlength="180" value="${e(handover.task)}"><small>One task per project. Use {project} and {client}; no message is sent.</small></label><p class="rule-issue" id="process-task-issue" role="status"></p><button class="button small" id="process-contextual-task">Use contextual receipt task</button><div class="process-task-examples" id="process-task-examples"></div>
      <label class="checkbox-row"><input type="checkbox" id="confirm-process"><span>I confirm these data bindings, actions and the selected change-request policy.</span></label><button class="button primary" id="open-process">Confirm & open application ${icon('arrow')}</button><p class="review-footer">The original Meta response stays unchanged in the recovery receipt. Unconfirmed actions remain blocked.</p></section></div>`;
    function preview(){
      root.querySelector('#process-task-issue').textContent=engine.taskIssue(project);
      root.querySelector('#process-task-examples').innerHTML=parent.rows.slice(0,4).map(id=>{const page=lookup.get(id);return `<div><strong>${e(page.title)}</strong><p>${e(global.ExitForge.followupText(handover.task,page))||'No receipt task selected.'}</p></div>`;}).join('');
    }
    function dirty(){p.confirmed=false;options.onDirty();preview();root.querySelector('#confirm-process').checked=false;}
    root.querySelector('#process-parent-policy').onchange=event=>{p.parent_revision=event.target.value==='__keep__'?'':event.target.value||null;dirty();};
    root.querySelector('#process-task-template').oninput=event=>{handover.task=event.target.value.trim();dirty();};
    root.querySelector('#process-contextual-task').onclick=()=>{handover.task='Confirm {client} received {project}.';root.querySelector('#process-task-template').value=handover.task;dirty();options.toast('Contextual wording selected by you. Original Meta output is preserved.');};
    root.querySelector('#open-process').onclick=()=>{
      if(p.parent_revision===null||p.parent_revision===undefined){options.toast('Choose what happens to the parent after a change request.',true);root.querySelector('#process-parent-policy').focus();return;}
      if(!root.querySelector('#confirm-process').checked){options.toast('Confirm the reviewed process before opening it.',true);return;}
      try{const next=structuredClone(project);next.process.confirmed=true;global.ExitForgeWorkspace.validateWorkspace(next);options.onConfirm(next);}
      catch(error){options.toast(error.message,true);}
    };
    root.querySelector('#process-review-receipt').onclick=()=>download(new Blob([JSON.stringify(global.ExitForgeWorkspace.recoveryReceipt(project),null,2)],{type:'application/json'}),filename(project.name)+'-process-review.json');
    preview();
  }
  global.ExitForgeProcessStudio={inputHTML,bindInput,review};
})(window);
