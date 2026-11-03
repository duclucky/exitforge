/* Review disclosure choices before downloading a project-only local handoff. */
(function(global){
  'use strict';
  function open(dialog,getData,parentId,returnFocus){
    const {escape:e,download,icon}=global.ExitForge,pack=global.ExitForgeHandoff;
    const initial=pack.preview(getData(),parentId);
    dialog.setAttribute('aria-label','Client handoff preview');
    dialog.classList.add('handoff-dialog');
    dialog.innerHTML=`<div class="handoff-scroll"><div class="dialog-top"><span class="eyebrow">ONE PROJECT · LOCAL DOWNLOAD</span><button class="icon-button" data-close-handoff aria-label="Close handoff preview">${icon('close')}</button></div><h2>Client handoff</h2><p>Prepare a read-only offline page and selected files for <strong>${e(initial.project.client)}</strong>. Your full editable application stays separate.</p>
      <div class="handoff-eligibility" data-handoff-eligibility role="status"></div><section class="handoff-summary" aria-label="Included records"><span class="eyebrow">ALWAYS INCLUDED · THIS PROJECT ONLY</span><h3>${e(initial.project.title)}</h3><p>Client: ${e(initial.project.client)} · Local state: ${e(initial.project.state)}</p><ul>${initial.items.map(item=>`<li><strong>${e(item.title)}</strong><span>${e(item.state)}</span></li>`).join('')}</ul></section>
      <fieldset class="handoff-choices"><legend>Choose what else to include</legend><label class="checkbox-row"><input type="checkbox" data-handoff-include-notes aria-label="Include working notes"><span>Include working notes<small>Project and item notes, as currently written. Inspect them below before sharing.</small></span></label><div class="handoff-assets">${initial.available.length?initial.available.map(file=>`<label class="checkbox-row"><input type="checkbox" data-handoff-asset value="${e(file.id)}"><span>${e(file.name)}<small>${file.bytes.toLocaleString('en-US')} bytes · ${e(file.mime)}</small></span></label>`).join(''):'<p>No attached files in this project.</p>'}</div></fieldset>
      <details class="handoff-note-review" hidden><summary>Review included notes</summary><div data-handoff-notes></div></details>
      <p class="handoff-disclosure">Review notes and selected files before sharing: their content is not automatically redacted. ZIP contents are unencrypted.</p><p class="review-footer">Statuses reflect your local workflow. The ZIP downloads to this device; you choose how to share it.</p>
      <p class="record-error" role="alert" hidden></p></div><div class="handoff-bottom"><div class="button-row handoff-actions"><button class="button primary" data-download-handoff>Download handoff ZIP ${icon('download')}</button><button class="button" data-close-handoff>Close preview</button></div><p class="review-footer" data-handoff-selection></p></div>`;
    const settings=()=>({includeNotes:dialog.querySelector('[data-handoff-include-notes]').checked,assetIds:Array.from(dialog.querySelectorAll('[data-handoff-asset]:checked')).map(input=>input.value)});
    function refresh(){
      const view=pack.preview(getData(),parentId,settings()),status=dialog.querySelector('[data-handoff-eligibility]');
      status.classList.toggle('ready',view.eligible);status.textContent=view.eligible?'Ready · This project can be packaged.':view.reasons.join(' ');
      dialog.querySelector('[data-download-handoff]').disabled=!view.eligible;
      dialog.querySelector('[data-handoff-selection]').textContent=`1 project · ${view.items.length} linked items · ${view.files.length} selected files · working notes ${view.selection.includeNotes?'included':'excluded'}. Extract the ZIP, then open index.html.`;
      const notes=dialog.querySelector('.handoff-note-review');notes.hidden=!view.selection.includeNotes;
      dialog.querySelector('[data-handoff-notes]').innerHTML=view.selection.includeNotes?[view.project,...view.items].map(record=>`<article><h3>${e(record.title)}</h3><pre>${e(record.notes)}</pre></article>`).join(''):'';
    }
    dialog.querySelectorAll('input').forEach(input=>input.onchange=()=>{dialog.querySelector('[role=alert]').hidden=true;try{refresh();}catch(error){showError(error);}});
    function showError(error){const alert=dialog.querySelector('[role=alert]');alert.textContent=error.message;alert.hidden=false;}
    dialog.querySelectorAll('[data-close-handoff]').forEach(button=>button.onclick=()=>dialog.close());
    dialog.onclose=()=>{dialog.classList.remove('handoff-dialog');returnFocus?.focus();};
    dialog.querySelector('[data-download-handoff]').onclick=()=>{
      try{const result=pack.build(getData(),parentId,settings());download(new Blob([result.bytes],{type:'application/zip'}),result.filename);}
      catch(error){showError(error);try{refresh();}catch(_){dialog.querySelector('[data-download-handoff]').disabled=true;}}
    };
    refresh();dialog.showModal();dialog.querySelector('[data-close-handoff]').focus();
  }
  global.ExitForgeHandoffView={open};
})(window);
