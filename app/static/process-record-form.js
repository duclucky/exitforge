/* Accessible record forms shared by studio and independent application. */
(function(global){
  'use strict';
  function open(dialog,data,options){
    const {escape:e}=global.ExitForge,records=global.ExitForgeProcessRecords;
    const record=data.pages.find(page=>page.id===options.id),editing=!!record;
    const role=editing?['parent','child'].find(role=>data.databases.find(db=>db.id===data.process[role+'_db']).rows.includes(record.id)):options.role;
    const parent=data.pages.find(page=>page.id===options.parent);
    const title=editing?'Edit record':role==='parent'?'Create project':'Create linked item';
    const fields=records.fields(data,role),states=records.initialStates(data,role);
    dialog.setAttribute('aria-label',title);
    dialog.innerHTML=`<form class="record-form" novalidate><div class="dialog-top"><span class="eyebrow">${editing?'YOUR CURRENT WORK':'CREATED IN EXITFORGE'}</span><button type="button" class="icon-button" data-record-cancel aria-label="Close record form">${global.ExitForge.icon('close')}</button></div><h2>${title}</h2><p>${editing?'Edit the record without changing its workflow state or relationship.':'This adds a local record to your independent application. It does not change the original export or call an AI provider.'}</p>
      ${role==='child'?`<div class="record-parent"><span class="eyebrow">LINKED PROJECT</span><strong>${e(parent?.title||data.pages.find(page=>page.id===data.process.links.find(link=>link.child===record?.id)?.parent)?.title||'')}</strong><small>The relationship stays fixed in this form.</small></div>`:''}
      <label class="field">${editing?'Record name':role==='parent'?'Project name':'Item name'}<input name="record-title" value="${e(record?.title||'')}" maxlength="160" required autocomplete="off"></label>
      ${!editing?`<label class="field">Initial stage<select name="record-stage" aria-label="Initial stage" aria-describedby="record-stage-help" required><option value="">Choose a starting stage…</option>${states.map(state=>`<option value="${e(state)}">${e(state)}</option>`).join('')}</select><small id="record-stage-help">Approval and handover remain separate reviewed actions.</small></label>`:`<p class="record-state">Current stage: <strong>${e(record.properties[data.process[role+'_field']])}</strong>. Use workflow actions to change it.</p>`}
      <div class="record-field-grid">${fields.map((field,index)=>`<label class="field">${e(field)}<input data-record-field="${index}" value="${e(record?.properties[field]||'')}" maxlength="500" autocomplete="off"></label>`).join('')}</div>
      <label class="field">Working notes<textarea name="record-body" rows="5" maxlength="20000">${e(record?.body||'')}</textarea></label>
      <p class="record-error" role="alert" hidden></p><div class="button-row record-form-actions"><button class="button primary" type="submit">${editing?'Save record':role==='parent'?'Create project':'Create item'}</button><button class="button" type="button" data-record-cancel>Cancel</button></div></form>`;
    dialog.querySelectorAll('[data-record-cancel]').forEach(button=>button.onclick=()=>dialog.close());
    dialog.onclose=()=>options.returnFocus?.focus();
    dialog.querySelector('form').onsubmit=event=>{
      event.preventDefault();const form=event.currentTarget;
      const input={title:form.querySelector('[name=record-title]').value,body:form.querySelector('textarea').value,
        properties:Object.fromEntries(fields.map((field,index)=>[field,form.querySelector(`[data-record-field="${index}"]`).value]))};
      try{
        const result=editing?records.edit(data,record.id,input):records.create(data,{...input,role,parent:role==='child'?parent.id:undefined,initial_state:form.querySelector('select').value});
        dialog.close();options.onCommit(result,role,editing);
      }catch(error){
        const message=form.querySelector('[role=alert]');message.textContent=error.message;message.hidden=false;
        message.setAttribute('tabindex','-1');message.focus();
      }
    };
    dialog.showModal();dialog.querySelector('[name=record-title]').focus();
  }
  global.ExitForgeProcessRecordForm={open};
})(window);
