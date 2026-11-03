/* Recovery studio. Source content is rendered as text; cloud actions are explicit. */
(function () {
  'use strict';
  const {escape:e,icon,download,filename}=ExitForge;
  const screen=document.getElementById('screen');
  const notice=document.getElementById('studio-notice');
  const drafts=new ExitForgeWorkspace.DraftStore({
    getItem:key=>localStorage.getItem(key),setItem:(key,value)=>localStorage.setItem(key,value),removeItem:key=>localStorage.removeItem(key)
  });
  const draftBar=document.createElement('div');
  draftBar.className='draft-toolbar';draftBar.hidden=true;
  draftBar.innerHTML='<span id="draft-status" role="status" aria-live="polite"></span><button class="button small" type="button">Back up current workspace</button>';
  notice.after(draftBar);
  let reviewDraft=null, draftTimer=null, draftEnabled=true;
  let demo=null;
  draftBar.querySelector('button').onclick=()=>{
    const current=controller?controller.getWorkspace():project;
    if(current)download(new Blob([JSON.stringify(current,null,2)],{type:'application/json'}),filename(current.name)+'.json');
  };
  let project=null, step=0, controller=null, providerStatus=null, screenshot=null, busy=false, trial=null;
  const steps=['Import workspace','Review recovery','Your workspace','Take it with you'];
  const labels=['Import','Review','Workspace','Export'];
  function message(text,error=false){notice.textContent=text;notice.classList.toggle('error',error);notice.classList.remove('loading');notice.hidden=!text;}
  function loading(text){message(text);notice.classList.add('loading');}
  function persistDraft(){
    clearTimeout(draftTimer);
    if(!project||!draftEnabled)return {ok:false};
    const result=drafts.save({project,step:Math.max(1,step),review:reviewDraft});
    draftBar.hidden=false;draftBar.classList.toggle('error',!result.ok);
    document.getElementById('draft-status').textContent=result.ok?'Draft saved on this device. Includes your workspace and attachments.':result.error;
    return result;
  }
  window.addEventListener('pagehide',()=>persistDraft());
  async function request(path,payload){
    const paid=['/api/enhance','/api/reconstruct-process'].includes(path);
    const headers={'Content-Type':'application/json','X-ExitForge':'studio-v1'};
    if(paid){
      await refreshHostedAI();
      if(providerStatus?.deployment?.mode==='public-demo'){
        if(!trial?.available)throw new Error(trial?.error||'The AI trial allowance is unavailable. Continue manual review or download your work.');
        headers['Idempotency-Key']=crypto.randomUUID();
      }
    }
    try{
      const response=await fetch(path,{method:'POST',headers,body:JSON.stringify(payload)});
      if(!response.ok){const data=await response.json();throw new Error(data.error||'The operation could not complete.');}
      return response;
    }finally{if(paid)await refreshHostedAI();}
  }
  async function refreshHostedAI(){
    try{
      providerStatus=await (await fetch('/api/status')).json();
      if(providerStatus.deployment?.mode==='public-demo'){
        if(providerStatus.trial?.shared_operations_remaining===0){
          trial={available:false,remaining:0,error:'The shared AI trial has reached its total allowance. Saved proposals, manual review and exports remain available.'};
        }else if(providerStatus.available_routes?.includes('baseten')){
          const response=await fetch('/api/ai/session');trial=await response.json();
          if(!response.ok)trial={available:false,error:trial.error};
        }else trial={available:false,error:providerStatus.deployment.notice};
        renderHostedAI();
      }
    }catch(_){trial={available:false,error:'AI availability could not be checked. Your source and manual workflow remain available.'};renderHostedAI();}
  }
  function renderHostedAI(){
    if(providerStatus?.deployment?.mode!=='public-demo')return;
    let panel=screen.querySelector('#hosted-ai-allowance');
    if(!panel){panel=document.createElement('section');panel.id='hosted-ai-allowance';panel.className='hosted-ai-allowance';panel.setAttribute('role','status');screen.prepend(panel);}
    panel.innerHTML=`<strong>${trial?.available?'Meta AI is ready for your export.':'AI trial currently unavailable.'}</strong><p>${trial?.available?`${trial.remaining} operation(s) available to this session, within the shared trial. No account connection or API key required.`:e(trial?.error||'This session, network or shared trial has reached its allowance. Continue manual review and export without AI.')}</p><small>One model call per operation. Failed attempts also use allowance. Two per session, three per network daily, subject to the shared budget. No automatic retry. Source excerpts may be shortened; review every proposal.</small>`;
    const route=document.getElementById('ai-route');
    if(route){
      route.value='baseten';const direct=route.querySelector('[value="direct"]');direct.disabled=true;direct.textContent='Direct Meta + Fireworks — unavailable here';
      document.getElementById('ai-route-description').textContent='Meta Muse Spark Open reads your source via Baseten in one model call. The app keeps its local view defaults. Direct Meta API and Fireworks are not called.';
      document.getElementById('ai-consent-description').textContent='Send the selected source excerpts and optional screenshot to Meta hosted by Baseten for this operation. Do not include data you are not authorized to share.';
      document.getElementById('cloud-consent').parentElement.querySelector('small').textContent='Uses one shared-trial operation, including a failed provider attempt. Your data is processed on this VPS and sent to Baseten only after you request AI.';
    }
    for(const id of ['run-ai','reconstruct-process']){const button=document.getElementById(id);if(button)button.disabled=busy||!trial?.available;}
    const observations=document.getElementById('process-observations');
    if(observations)observations.parentElement.querySelector('small').textContent='Hosted trial: one to four PNG/JPEG files, at most 1536 px per side, 1.6 megapixels and 2 MB each. Add in before/action/after order. Images are sent only for this operation.';
    const modal=document.getElementById('download-modal');
    if(modal){modal.disabled=true;modal.closest('section').querySelector('p').textContent='Modal is unavailable on this hosted trial. Download independent app above packages the same workspace on this VPS without a paid model call.';}
  }
  function workflowApproved(){return project?.process?project.process.confirmed:project?.workflow.confirmed;}
  function renderNav(){
    queueMicrotask(renderHostedAI);
    screen.closest('main').classList.toggle('process-workspace',!!project?.process&&step===2);
    document.querySelector('.app-shell').dataset.stage=String(step);
    screen.dataset.stage=step;screen.classList.toggle('demo-active',!!demo);screen.closest('main').classList.toggle('demo-session',!!demo);screen.closest('main').classList.toggle('demo-workspace',!!demo&&step===2);
    document.querySelector('.step-nav').innerHTML=steps.map((name,i)=>`<button class="step-button ${step===i?'active':''}" data-step="${i}" ${(!project&&i)||(i>1&&(!workflowApproved()||reviewDraft))?'disabled':''} aria-current="${step===i?'step':'false'}"><span class="step-number">${i+1}</span>${labels[i]}</button>`).join('');
    document.querySelectorAll('[data-step]').forEach(b=>b.onclick=()=>go(Number(b.dataset.step)));
    document.getElementById('current-step').textContent=steps[step];
  }
  function go(next,approved=false){
    if(busy)return;
    if(next>0&&!project)return;
    if(next>1&&(!workflowApproved()||reviewDraft)&&!approved){message('Confirm the reviewed workflow before opening or exporting the application.',true);return;}
    if(controller){project=controller.getWorkspace();controller=null;}
    step=next;message('');renderNav();
    [renderImport,renderReview,renderWorkspace,renderExport][step]();
    if(next>0)persistDraft();
    window.scrollTo({top:0,behavior:'instant'});
  }
  function intro(kicker,title,description,extra=''){
    return `<div class="intro-row"><div><span class="eyebrow">${kicker}</span><h1>${title}</h1><p>${description}</p></div>${extra}</div>`;
  }
  function demoProject(){return project?.pages.find(page=>page.id===demo?.pageId);}
  function demoGuide(){
    if(!demo)return '';
    return `<section class="demo-guide" role="region" aria-label="Guided demo"><div class="demo-heading"><div><span class="eyebrow">${isHandoff()?'CLIENT HANDOFF · ILLUSTRATIVE SCENARIO':'THE 3-MINUTE WALKTHROUGH'}</span><h2>${step===1?'Files are the starting point. You choose what comes next.':step===2?'Make the workflow earn your trust.':'Now close the studio. Keep the work.'}</h2></div><button class="button small" id="exit-demo">Exit guided demo</button></div><div id="demo-progress" aria-live="polite"></div></section>`;
  }
  function updateDemo(){
    const progress=document.getElementById('demo-progress');if(!demo||!progress)return;
    if(step===1){progress.innerHTML='<p>01 / Confirm a rule: inspect the source below, keep the checklist requirement, then explicitly confirm the delivery workflow. No AI or cloud call is needed for this local walkthrough.</p><button class="button small" id="jump-rule">Review delivery rule '+icon('arrow')+'</button>';
      document.getElementById('jump-rule').onclick=()=>{document.getElementById('confirm-rule').scrollIntoView({block:'center',behavior:'instant'});document.getElementById('confirm-rule').focus({preventScroll:true});};
    }
    else if(step===2){
      const page=demoProject();
      const delivered=!!page&&page.properties[project.workflow.field]===project.workflow.delivery_state&&page.checklist.every(item=>item.done)&&project.tasks.some(task=>task.id===`followup:${page.id}`);
      progress.innerHTML=`<ol class="demo-proof-list"><li data-proof="guard" data-complete="${demo.guard}"><span class="proof-number">${demo.guard?icon('check'):'1'}</span><div><strong>${demo.guard?'Delivery blocked by the actual rule':'Try delivering too early'}</strong><p>Open Brand launch. Set its stage to Delivered before final approval.</p></div></li><li data-proof="delivery" data-complete="${delivered}"><span class="proof-number">${delivered?icon('check'):'2'}</span><div><strong>${delivered?'Delivered + one follow-up present':'Complete approval. Deliver again.'}</strong><p>Check “Get final approval”, deliver, then inspect Follow-ups.</p></div></li><li><span class="proof-number">3</span><div><strong>Take the application with you</strong><p>Download it, disconnect, edit and reload in the independent file.</p></div></li></ol><button class="button small" id="open-demo-project">Open demo project ${icon('arrow')}</button>`;
      document.getElementById('open-demo-project').onclick=()=>controller?.openPage(demo.pageId,document.getElementById('open-demo-project'));
    }else{progress.innerHTML='<p>03 / Download the independent app below. Open the saved HTML file, disable the network, edit a project and reload. The studio cannot observe that separate file: verify the result there.</p>';}
    document.getElementById('exit-demo').onclick=()=>{demo=null;document.querySelector('.demo-guide')?.remove();renderNav();message('Guided demo closed. Your workspace and changes are kept.');};
  }
  function sourceComparison(){
    const source=demoProject()||project.pages.find(page=>page.checklist.length)||project.pages[0];
    return `<section class="recovery-story" aria-label="From archive to application"><div><span class="eyebrow">THE EXPORT IS ONLY THE BEGINNING</span><h2>Recover the content.<br>Rebuild the ability to act.</h2><p>The source gives you facts. Your confirmed rules make them useful again.</p></div><div class="recovery-outcomes"><div><span>FROM YOUR EXPORT</span><strong>${project.pages.length} pages · ${project.databases.length} database${project.databases.length===1?'':'s'}</strong><p>Original fields, checklist state, links and safe local files.</p></div><div><span>AFTER YOUR CONFIRMATION</span><strong>A working, independent application</strong><p>Editable views, with optional delivery checks and local follow-ups from the rules you choose below.</p></div></div></section><details class="source-inspector panel"><summary>Inspect recovered source</summary><p class="review-footer">Current recovered record, with its source reference. Workspace edits are reflected here; this preview does not establish original automations or permissions.</p>${source?`<div class="source-preview"><div><span class="eyebrow">SOURCE REFERENCE</span><strong>${e(source.title)}</strong><code>${e(source.source)}</code><dl>${Object.entries(source.properties).slice(0,6).map(([key,value])=>`<div><dt>${e(key)}</dt><dd>${e(value)}</dd></div>`).join('')}</dl></div><pre>${e(source.body||'No separate Markdown body was exported.')}</pre></div>`:'<p>No source pages were found.</p>'}</details>`;
  }
  function isHandoff(){return project?.provenance?.scenario==='client-handoff';}
  function metaDecision(){
    const ai=project.ai_review, spec=ai?.specification;
    return `<section class="meta-decision" aria-label="Meta contribution"><div><span class="eyebrow">SOURCE FACTS → META PROPOSAL → YOUR DECISION</span><h2>${ai?'Meta proposed. You decide.':'Let Meta read between the files.'}</h2>${project.provenance.recorded_example?'<span class="pill">RECORDED REAL META RUN · NOV 2 · SYNTHETIC DATA</span>':''}<p>${ai?'Compare the saved proposal with the rule you approve. Model output is evidence to review, not recovered automation.':'Muse Spark Open can identify the workflow field, explain missing context and propose a reusable local rule. Nothing activates without your review.'}</p></div><div class="button-row"><button class="button primary small" id="review-meta">${ai?'Inspect Meta reasoning':'Review with Meta AI'} ${icon('arrow')}</button><button class="button small" id="recovery-receipt">Download recovery receipt</button></div>${ai?`<div class="decision-columns"><div><span class="eyebrow">RECOVERED FILES</span><strong>${project.pages.length} pages · ${Object.keys(project.assets).length} attachments</strong><p>${project.provenance.parser_workflow?`Parser workflow: ${e(project.provenance.parser_workflow.field||'not selected')}. `:''}Field names and values are facts. Original automations are unknown.</p></div><div><span class="eyebrow">SAVED META PROPOSAL</span><strong>${e(spec.status_field||'No field')} → ${e(spec.delivery_state||'No delivery')}</strong><p>${ai.calls.filter(c=>c.status!=='failed').length} completed operation(s). ${e(ai.outcome==='partial'?'Setup incomplete.':'No new inference on this view.')}</p></div><div><span class="eyebrow">YOUR RULE</span><strong id="decision-rule"></strong><p id="decision-difference"></p></div></div>`:''}</section>`;
  }
  function downloadReceipt(){
    const receipt=ExitForgeWorkspace.recoveryReceipt(project);
    if(step===1)receipt.unconfirmed_review=reviewDraft||{name:document.getElementById('workspace-name').value,
      field:document.getElementById('status-field').value,followup:document.getElementById('followup-text').value};
    download(new Blob([JSON.stringify(receipt,null,2)],{type:'application/json'}),filename(project.name)+'-recovery-receipt.json');
  }
  function handoffContext(){
    if(!isHandoff())return '';
    return '<section class="handoff-context" aria-label="Client handoff scenario"><span class="eyebrow">ILLUSTRATIVE SCENARIO · AUTHORIZED EXPORT</span><strong>The agency engagement ended. Three client handoffs still need a home.</strong><p>Avery has an export saved before access ended. Finish the Northstar logo pack: retain the brief and client context, record final approval, then create a receipt-check task. No original account is connected.</p><small>Fictional scenario, not a customer testimonial. Production artwork is not included.</small></section>';
  }
  function renderImport(){
    screen.innerHTML=`<section class="landing-hero" aria-label="Your work, independent"><div class="hero-copy"><span class="reference-tag">FOR INDEPENDENT WORK · KEEP YOUR NEXT CHAPTER</span><h1>The contract ends.<br><span class="headline-highlight">Your work continues.</span></h1><p>Keep the context. Finish the handoff. Turn an authorized workspace export into an application you can keep using.</p><strong class="hero-invitation">Start with your export, or explore a client handoff.</strong><div class="hero-buttons"><button class="button primary" id="linked-process-demo">Rebuild a working process <span aria-hidden="true">↗</span></button><button class="button" id="editorial-process-demo">Try editorial workflow <span aria-hidden="true">↗</span></button><button class="button" id="try-handoff">Try client handoff <span aria-hidden="true">↗</span></button><button class="button" id="hero-import">Use your own export <span aria-hidden="true">↗</span></button></div><p class="hero-note">Fictional sources. Both workflow examples use saved actual Meta results; opening them makes no new API call or account connection.</p><button class="button small meta-example-button" id="meta-example">Explore Meta-assisted example ${icon('arrow')}</button><p class="hero-note">Actual saved Meta response · synthetic localization export · no new API call.</p><small>You choose the rules. Nothing is delivered or sent automatically.</small></div><figure class="hero-art"><div class="art-sticker">YOUR WORK.<br>STILL YOURS.</div><div class="continuity-graphic" role="img" aria-label="Illustration: a ZIP export becomes an editable offline HTML application after you review its rules."><div class="graphic-title"><span class="graphic-symbol" aria-hidden="true">${icon('link')}</span><div><strong>WORKSPACE CONTINUITY</strong><small>ILLUSTRATION · NOT A LIVE RECOVERY</small></div><span aria-hidden="true">↗</span></div><div class="format-pair"><div class="format-card source-format"><span class="format-caption">01 / YOUR EXPORT</span><div class="mini-source" aria-hidden="true"><i></i><i></i><i></i><i></i></div><strong class="format-name">ZIP</strong><span>Pages. Links. Local files.</span></div><div class="format-card app-format"><span class="format-caption">02 / YOUR APPLICATION</span><div class="mini-application" aria-hidden="true"><i></i><div><b></b><b></b><b></b></div></div><strong class="format-name">HTML</strong><span>Editable. Offline. Yours.</span></div></div><div class="graphic-proof"><span aria-hidden="true">${icon('check')}</span><div><strong>Rules you review. Work you keep.</strong><small>Original permissions and automations are not recreated.</small></div></div></div><figcaption>Illustration · Authorized export → reviewed rules → independent app.<br>Try the sample to inspect the source and finish a real local workflow.</figcaption></figure></section><section class="recovery-tools" id="recovery-tools" aria-label="Import your workspace"><div class="section-heading"><span class="reference-tag">01 / BRING THE SOURCE</span><h2>Your next chapter starts here.</h2><p>Use an export you are allowed to keep. Review every rule before it runs.</p></div>`+
      `<div class="import-layout"><section class="upload-card"><div class="panel-heading">Start with your workspace<span class="step-tag">01 / RECOVER</span></div><div class="dropzone" id="dropzone"><div><div class="upload-symbol">${icon('download')}</div><h2>Bring your work with you.</h2><p>Drop your Notion Markdown &amp; CSV export here.</p><button type="button" class="button primary" id="choose-export">Choose export ZIP ${icon('arrow')}</button><input id="workspace-file" type="file" accept=".zip,.json" hidden><div class="upload-meta">ZIP up to 20 MB · local attachments included<br>ExitForge JSON backups are also supported.</div></div></div><div class="sample-row"><div><strong>Explore a complete recovery</strong><p>30 sample projects, client pages and a delivery workflow.</p></div><div class="sample-actions"><button class="button primary small" id="start-demo">Start guided demo ${icon('arrow')}</button><button class="button small ghost" id="load-sample">Try sample workspace</button></div></div></section><aside class="promise-card"><span class="eyebrow">MORE THAN A FOLDER OF FILES</span><h2>Keep the work.<br>Recover the workflow.</h2><p>A portable application built around the data you already have.</p><div class="recovery-diagram"><div class="diagram-node">${icon('file')}<span><strong>Workspace export</strong><small>Pages, records and attachments</small></span></div><div class="diagram-connector"></div><div class="diagram-node">${icon('link')}<span><strong>Review &amp; reconnect</strong><small>Source facts + rules you confirm</small></span></div><div class="diagram-connector"></div><div class="diagram-node final">${icon('board')}<span><strong>Your independent app</strong><small>Editable. Offline. Yours.</small></span></div></div><div class="promise-foot">${icon('check')} You can export your work from ExitForge, too.</div></aside></div><div class="principles"><div class="principle">${icon('file')}<div><strong>Your original stays untouched</strong><p>Read an export. Keep its source references and local files together.</p></div></div><div class="principle">${icon('check')}<div><strong>You decide how it works</strong><p>Missing automations stay off until you explicitly confirm the rules.</p></div></div><div class="principle">${icon('download')}<div><strong>Keep a working application</strong><p>Download one HTML file. No subscription or server is needed to use it.</p></div></div></div></section>`;
    const saved=drafts.load();
    if(saved.draft||saved.error){
      const summary=saved.draft?`<strong>${e(saved.draft.review?.name||saved.draft.project.name)}</strong><p>${saved.draft.project.pages.length} pages · Saved ${e(new Date(saved.draft.saved_at).toLocaleString())}. Stored in this browser, including attachments.</p>`:`<p>${e(saved.error)}</p>`;
      document.getElementById('recovery-tools').insertAdjacentHTML('beforebegin',`<section class="saved-draft panel"><div><span class="eyebrow">CONTINUE YOUR RECOVERY</span>${summary}</div><div class="button-row">${saved.draft?'<button class="button primary" id="resume-draft">Resume saved workspace</button>':''}<button class="button small" id="remove-draft">Remove saved draft</button></div></section>`);
      document.getElementById('resume-draft')?.addEventListener('click',()=>{
        const current=drafts.load();
        if(!current.draft){message(current.error||'This draft is no longer available.',true);return;}
        project=current.draft.project;reviewDraft=current.draft.review||null;screenshot=null;draftEnabled=true;demo=null;
        go(Math.max(1,current.draft.step));message('Saved workspace resumed. Cloud consent must be given again for each operation.');
      });
      document.getElementById('remove-draft').onclick=()=>{
        const result=drafts.clear();
        if(!result.ok){message(result.error,true);return;}
        draftEnabled=false;draftBar.hidden=true;renderImport();message('Saved draft removed from this browser. An open workspace remains in this tab.');
      };
    }
    document.getElementById('choose-export').onclick=()=>document.getElementById('workspace-file').click();
    document.getElementById('workspace-file').onchange=event=>{if(event.target.files[0])importFile(event.target.files[0]);};
    const zone=document.getElementById('dropzone');
    zone.ondragover=event=>{event.preventDefault();zone.classList.add('dragover');};
    zone.ondragleave=()=>zone.classList.remove('dragover');
    zone.ondrop=event=>{event.preventDefault();zone.classList.remove('dragover');if(event.dataTransfer.files[0])importFile(event.dataTransfer.files[0]);};
    const loadSample=async(guided=false,scenario='studio')=>{
      if(busy)return;
      try{
        busy=true;loading('Opening the purpose-created sample workspace…');
        const response=await fetch('/api/sample'+(scenario==='client-handoff'?'?scenario=client-handoff':''),{signal:AbortSignal.timeout(15000)});
        if(response.status!==200||!response.headers.get('Content-Type')?.includes('application/json'))throw new Error('The sample export was unavailable. Reload the studio and try again.');
        const source=await response.json();
        if(typeof source.archive_base64!=='string'||!source.archive_base64.length)throw new Error('The sample export was empty. Reload the studio and try again.');
        const bytes=Uint8Array.from(atob(source.archive_base64),character=>character.charCodeAt(0));
        const file=new File([bytes],scenario==='client-handoff'?'client-handoff-demo.zip':'Northstar workspace.zip',{type:'application/zip'});
        busy=false;await importFile(file,true,guided,scenario);
      }catch(error){busy=false;message(error.name==='TimeoutError'?'The sample request timed out. Check the local server and try again.':error.message,true);}
    };
    document.getElementById('load-sample').onclick=()=>loadSample();
    document.getElementById('start-demo').onclick=()=>loadSample(true);
    document.getElementById('try-handoff').onclick=()=>loadSample(true,'client-handoff');
    const openRecordedProcess=async(domain)=>{
      if(busy)return;
      try{const response=await fetch('/api/process-example?domain='+domain);if(!response.ok)throw new Error('Linked example unavailable.');
        const data=await response.json();await importFile(new File([JSON.stringify(data)],'recorded-'+domain+'-process.json',{type:'application/json'}));
      }catch(error){message(error.message,true);}
    };
    document.getElementById('linked-process-demo').onclick=()=>openRecordedProcess('delivery');
    document.getElementById('editorial-process-demo').onclick=()=>openRecordedProcess('editorial');
    document.getElementById('meta-example').onclick=async()=>{
      if(busy)return;
      try{
        const response=await fetch('/api/meta-example');
        if(!response.ok)throw new Error('Recorded example unavailable. Your saved draft is unchanged.');
        const data=await response.json();
        await importFile(new File([JSON.stringify(data)],'recorded-meta-example.json',{type:'application/json'}));
      }catch(error){message(error.message,true);}
    };
    document.getElementById('hero-import').onclick=()=>{
      document.getElementById('recovery-tools').scrollIntoView({block:'start',behavior:'instant'});
      document.getElementById('choose-export').focus({preventScroll:true});
    };
  }
  async function importFile(file,sample=false,guided=false,scenario='studio'){
    if(busy)return;
    busy=true;loading('Recovering source pages, linked records and local attachments…');
    try{
      if(!file.size)throw new Error('This file is empty. Choose a non-empty ZIP or JSON backup.');
      if(file.size>20*1024*1024)throw new Error('Choose an export smaller than 20 MB.');
      let result;
      if(file.name.toLowerCase().endsWith('.json')){
        const data=JSON.parse(await file.text());result=await (await request('/api/validate',{project:data})).json();
      }else{
        const response=await fetch('/api/import',{method:'POST',headers:{'X-ExitForge':'studio-v1','X-Filename':encodeURIComponent(file.name),'Content-Type':'application/zip'},body:file});
        result=await response.json();if(!response.ok)throw new Error(result.error);
      }
      if(sample){result.name=scenario==='client-handoff'?"Avery's handoff desk":'Northstar workspace';result.provenance.sample=true;if(scenario==='client-handoff')result.provenance.scenario=scenario;}
      ExitForgeWorkspace.validateWorkspace(result);
      project=result;screenshot=null;reviewDraft=null;draftEnabled=true;
      demo=guided?{pageId:project.pages.find(page=>page.title==='Brand launch')?.id,guard:false}:null;
      busy=false;go(1);
      message(project.process_review?.recorded?'Recorded actual Meta proposal opened. Synthetic source; no new inference request.':sample?'Sample workspace recovered. This is purpose-created demo data; no AI calls have been made.':'Export recovered locally. Review source facts and confirm the behavior you want to keep.');
      if(result.provenance.recorded_example){
        const recordedDate=result.process_review?.recorded_on||result.provenance.recorded_example.date;
        const date=typeof recordedDate==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(recordedDate)?' from '+recordedDate:'';
        message('Recorded real Meta example'+date+'. Synthetic source data; opening it makes no new API call. Review before activation.');
      }
    }catch(error){busy=false;message(error.message,true);}
  }
  function cloudPanel(ai){
    const route=ai?.route||'baseten',partial=ai?.outcome==='partial';
    const sources=Array.isArray(ai?.specification?.evidence_sources)?ai.specification.evidence_sources:[];
    const references=sources.length?`<details class="ai-evidence" style="margin:12px 0"><summary>Source references used by the model (${sources.length})</summary><ul>${sources.map(source=>`<li><code style="white-space:normal;overflow-wrap:anywhere">${e(source)}</code></li>`).join('')}</ul></details>`:'';
    const provenance=route==='baseten'?'Meta open weights served by Baseten. Direct Meta API and Fireworks were not called; templates came from the curated list.':partial?
      (ai.template_selection==='fireworks_reranked'?'Meta API interpretation and Fireworks ranking completed; view configuration did not.':'Meta API interpretation completed; Fireworks ranking did not complete. No Baseten view configuration was attempted.'):
      'Direct Meta API interpretation, Fireworks template ranking and Baseten view configuration.';
    return `<details class="panel cloud-options" style="margin-top:20px" ${partial||ai?.trial?'open':''}>
      <summary>Optional: interpret with Meta AI <span class="code-label">CLOUD STEP</span></summary>
      ${partial?`<section class="warning-box partial-recovery" aria-label="Incomplete AI setup"><span class="eyebrow">INTERPRETATION RETAINED</span><h3>Keep the useful result. Finish the setup manually.</h3><p>${e(ai.warning)}</p><button class="button small" id="continue-manual-review">Continue manual review ${icon('arrow')}</button><p class="review-footer">Your source data is kept; no replacement view was applied. No new AI call is needed to review, confirm and export locally.</p></section>`:''}
      <label class="field">AI route<select id="ai-route" aria-label="AI route"><option value="baseten" ${route==='baseten'?'selected':''}>Meta open weights via Baseten</option><option value="direct" ${route==='direct'?'selected':''}>Direct Meta API + Fireworks + Baseten</option></select></label>
      <p id="ai-route-description"></p><label class="field">Optional workflow screenshot<input id="screenshot" type="file" accept="image/png,image/jpeg"><small>PNG or JPEG, up to 2 MB. Kept in memory until you request cloud interpretation.</small></label>
      <label class="checkbox-row"><input id="cloud-consent" type="checkbox"><span><span id="ai-consent-description"></span><small>Provider usage may incur charges. Cloud recovery must also be enabled on the server. Up to two model calls on the Baseten route; no automatic retries.</small></span></label>
      ${ai?'<p class="review-footer">Starting again repeats interpretation and subsequent setup steps. Completed calls are not reused and may incur charges again. Existing results remain available unless replaced by a new validated proposal.</p>':''}
      <div class="button-row"><button class="button small" id="run-ai">${ai?'Interpret again':'Interpret workflow'} ${icon('arrow')}</button><button class="button small ghost" data-connections>View connections</button></div>
      ${ai?`<section class="warning-box" aria-label="AI proposal" tabindex="-1"><h3>${partial?'Source interpretation — setup incomplete':'Model proposal — review before activation'}</h3><p>${e(provenance)}</p><p>${e(ai.specification.rationale)}</p>${references}<ul class="warning-list">${ai.specification.unknowns.map(x=>`<li>${e(x)}</li>`).join('')}</ul><ul class="warning-list">${ai.calls.map(c=>`<li>${e(c.provider)} · ${e(c.model)} · ${e(c.operation||'inference')}${c.status==='failed'?' · failed (usage may still apply)':''} · ${c.elapsed_ms} ms</li>`).join('')}</ul></section>`:''}
      <p class="review-footer">A selected route never falls back to another provider. Local parsing remains available without API calls.</p></details>`;
  }
  function renderReview(){
    if(project.process){
      ExitForgeProcessStudio.review(screen,project,{
        onDirty:()=>{reviewDraft=null;persistDraft();renderNav();},
        onConfirm:next=>{project=next;reviewDraft=null;go(2,true);},toast:message
      });return;
    }
    const links=project.pages.reduce((count,p)=>count+p.links.filter(l=>l.target).length,0);
    const candidates=project.pages.reduce((count,p)=>count+p.relations.filter(l=>!l.confirmed).length,0);
    const fields=[...new Set(project.databases.flatMap(d=>d.fields))];
    const field=project.workflow.field;
    const states=project.workflow.states;
    const suggestedDelivery=project.workflow.delivery_state||states.find(s=>/deliver|complete|done|closed/i.test(s))||'';
    const ai=project.ai_review;
    screen.innerHTML=intro('RECOVERED FACTS. EXPLICIT CHOICES.','Make the connections.<br>Keep the behavior.','Your export contains data. Some views and rules need your input. Review what survived, then decide how your independent application should work.')+
      demoGuide()+handoffContext()+metaDecision()+ExitForgeProcessStudio.inputHTML(project)+sourceComparison()+`<div class="review-grid"><div><section class="panel"><div class="panel-heading">Recovery summary<span class="pill local">${project.provenance.sample?'Sample data':'Local recovery'}</span></div><label class="field">Workspace name<input id="workspace-name" value="${e(project.name)}" maxlength="100"></label><div class="stats-row"><div class="stat"><strong>${project.pages.length}</strong><span>pages recovered</span></div><div class="stat"><strong>${links}</strong><span>explicit page links</span></div><div class="stat"><strong>${Object.keys(project.assets).length}</strong><span>local attachments</span></div></div><div class="evidence-list"><div class="evidence-row">${icon('file')}<div><strong>Source records &amp; checklist state</strong><small>${project.databases.length} database · exact field names and values retained</small></div><span class="pill local">Recovered</span></div><div class="evidence-row">${icon('link')}<div><strong>Page-to-page connections</strong><small>Explicit paths and source IDs; ambiguous matches stay unresolved</small></div><span class="pill local">Source-linked</span></div><div class="evidence-row">${icon('task')}<div><strong>Views &amp; automation behavior</strong><small>Exported files do not establish every rule or permission</small></div><span class="pill warn">Your input</span></div></div>${candidates?`<label class="checkbox-row"><input id="accept-relations" type="checkbox"><span>Confirm ${candidates} unique title matches as page relations.<small>These are suggestions, not explicit links from the source. Ambiguous titles remain unresolved.</small></span></label>`:''}<details class="warning-box"><summary>Recovery limits &amp; unresolved items (${project.warnings.length})</summary><ul class="warning-list">${project.warnings.slice(0,40).map(w=>`<li>${e(w)}</li>`).join('')}</ul></details></section>${cloudPanel(ai)}</div>
      <section class="panel"><div class="panel-heading"><h2>Declare your delivery workflow</h2><span class="pill warn">${project.workflow.confirmed?'Previously confirmed':'Needs confirmation'}</span></div><p>These are rules you choose for the new application. They are not claimed to have been recovered automatically.</p><label class="field">Status field<select id="status-field"><option value="">No workflow field</option>${fields.map(f=>`<option ${f===field?'selected':''}>${e(f)}</option>`).join('')}</select></label><label class="field">Workflow stages<input id="workflow-states" value="${e(states.join(', '))}"><small>Comma-separated values. Add a stage only if you want to declare it.</small></label><label class="field">Delivery stage<select id="delivery-state"><option value="">No delivery automation</option>${states.map(s=>`<option ${s===suggestedDelivery?'selected':''}>${e(s)}</option>`).join('')}</select></label><label class="checkbox-row"><input id="require-checklist" type="checkbox" ${project.workflow.require_checklist?'checked':''}><span>Require every checklist item before delivery.</span></label><p class="checklist-warning" id="checklist-warning" role="status" hidden></p><label class="field">Local follow-up task<input id="followup-text" value="${e(project.workflow.followup||(isHandoff()?'Confirm {client} received {project}.':'Check in after delivery'))}" maxlength="180"><small>One local task per delivered project. Use {project} for its title and {client} for its Client or Customer field. No email is sent.</small></label><div class="followup-preview" id="followup-preview" role="status" aria-live="polite"></div><label class="checkbox-row"><input id="confirm-rule" type="checkbox"><span>I confirm this workflow for the new application.<small>Source permissions, integrations and team collaboration are not recreated.</small></span></label><button class="button primary" id="confirm-workflow" style="width:100%">Confirm &amp; open workspace ${icon('arrow')}</button><div class="review-footer">You can return here to change your rule. Existing follow-up tasks are kept.</div></section></div>`;
    ExitForgeProcessStudio.bindInput(screen,async observations=>{
      if(busy)throw new Error('Another operation is in progress.');
      busy=true;loading('Meta is reading the related records and ordered observations…');
      try{
        const result=await (await request('/api/reconstruct-process',{project,observations,consent:true})).json();
        project.process=result.process;
        project.process_review={proposal:structuredClone(result.process),observations:result.observations,calls:result.calls,question:result.question,recorded:false};
        if(result.model_proposal)project.process_review.model_proposal=structuredClone(result.model_proposal);
        if(result.binding_resolution)project.process_review.binding_resolution=structuredClone(result.binding_resolution);
        project.provenance.cloud_calls.push(...result.calls);reviewDraft=null;demo=null;
        busy=false;go(1);message('Linked process proposed. Inspect the evidence and resolve the change-request policy before activation.');
      }finally{busy=false;}
    },message);
    updateDemo();
    document.getElementById('status-field').onchange=event=>{
      const values=[...new Set(project.pages.map(p=>p.properties[event.target.value]).filter(Boolean))];
      document.getElementById('workflow-states').value=values.join(', ');updateDelivery(values);
    };
    document.getElementById('workflow-states').onchange=event=>updateDelivery(event.target.value.split(',').map(x=>x.trim()).filter(Boolean));
    document.getElementById('confirm-workflow').onclick=()=>{
      if(!document.getElementById('confirm-rule').checked){message('Confirm the workflow before opening the application.',true);return;}
      const name=document.getElementById('workspace-name').value.trim();
      const statusField=document.getElementById('status-field').value;
      const stages=[...new Set(document.getElementById('workflow-states').value.split(',').map(x=>x.trim()).filter(Boolean))];
      if(!name){message('Enter a workspace name.',true);return;}
      if(statusField&&(!stages.length||stages.length>8)){message('Choose between one and eight workflow stages.',true);return;}
      const observed=project.pages.filter(p=>p.database).map(p=>p.properties[statusField]).filter(Boolean);
      if(statusField&&observed.some(v=>!stages.includes(v))){message('Keep existing source stages so no records disappear from the board.',true);return;}
      const delivery=document.getElementById('delivery-state').value;
      const taskRule={field:statusField,delivery_state:delivery,followup:document.getElementById('followup-text').value.trim()};
      const taskReview=ExitForgeWorkspace.followupReview(project,taskRule);
      if(taskReview.issue){message(taskReview.issue,true);document.getElementById('followup-text').focus();return;}
      project.name=name;
      project.workflow={field:statusField,states:statusField?stages:[],delivery_state:delivery,
        require_checklist:document.getElementById('require-checklist').checked,
        followup:delivery?document.getElementById('followup-text').value.trim():'',confirmed:true,
        basis:'Explicitly declared and confirmed by the user',confirmed_at:new Date().toISOString()};
      if(document.getElementById('accept-relations')?.checked)project.pages.forEach(p=>p.relations.forEach(r=>r.confirmed=true));
      if(demo)demo.guard=false;reviewDraft=null;go(2,true);
    };
    document.getElementById('screenshot').onchange=event=>{
      const file=event.target.files[0];if(!file){screenshot=null;return;}
      if(file.size>2*1024*1024){message('Choose a screenshot smaller than 2 MB.',true);event.target.value='';return;}
      const reader=new FileReader();reader.onload=()=>screenshot=reader.result;reader.readAsDataURL(file);
    };
    document.getElementById('run-ai').onclick=runAI;
    document.getElementById('review-meta').onclick=()=>{
      const panel=document.querySelector('.cloud-options');panel.open=true;
      panel.scrollIntoView({block:'start',behavior:'instant'});
      (project.ai_review?panel.querySelector('[aria-label="AI proposal"]'):document.getElementById('ai-route')).focus({preventScroll:true});
    };
    document.getElementById('recovery-receipt').onclick=downloadReceipt;
    document.getElementById('continue-manual-review')?.addEventListener('click',()=>{
      const confirm=document.getElementById('confirm-rule');confirm.scrollIntoView({block:'center',behavior:'instant'});confirm.focus({preventScroll:true});
      message('Interpretation retained. Review the fields and confirm your workflow; this makes no new AI call.');
    });
    const routeControl=document.getElementById('ai-route');
    function describeRoute(){
      const baseten=routeControl.value==='baseten';
      document.getElementById('ai-route-description').textContent=baseten?'Muse Spark Open interprets source evidence and configures a view through Baseten. Uses the exact hackathon model. Direct Meta API and Fireworks are not called; templates are curated without reranking.':'Meta API interprets the evidence, Fireworks ranks templates, then Baseten configures a view. Requires all three credentials and usable provider access.';
      document.getElementById('ai-consent-description').textContent=baseten?'Send source text and this screenshot to Baseten for this operation.':'Send source text and this screenshot to Meta API, with the resulting specification sent to Fireworks and Baseten for this operation.';
      document.getElementById('cloud-consent').checked=false;
    }
    routeControl.onchange=describeRoute;describeRoute();
    screen.querySelector('[data-connections]').onclick=showConnections;
    if(reviewDraft){
      document.getElementById('workspace-name').value=reviewDraft.name;
      document.getElementById('status-field').value=reviewDraft.field;
      document.getElementById('workflow-states').value=reviewDraft.states;
      updateDelivery(reviewDraft.states.split(',').map(x=>x.trim()).filter(Boolean));
      document.getElementById('delivery-state').value=reviewDraft.delivery;
      document.getElementById('followup-text').value=reviewDraft.followup;
      document.getElementById('require-checklist').checked=reviewDraft.requireChecklist;
      if(document.getElementById('accept-relations'))document.getElementById('accept-relations').checked=reviewDraft.acceptRelations;
    }
    function updateFollowupPreview(){
      const template=document.getElementById('followup-text').value.trim();
      const preview=document.getElementById('followup-preview');
      const enabled=!!document.getElementById('delivery-state').value&&!!template;
      const rule={field:document.getElementById('status-field').value,delivery_state:document.getElementById('delivery-state').value,followup:template};
      const review=ExitForgeWorkspace.followupReview(project,rule);
      const examples=review.records.slice(0,6);
      const unfinished=review.records.filter(page=>page.checklist.some(item=>!item.done)).length;
      const checklistWarning=document.getElementById('checklist-warning');
      checklistWarning.hidden=!rule.delivery_state||document.getElementById('require-checklist').checked||!unfinished;
      checklistWarning.textContent=`${unfinished} projects have unfinished checklists. This rule allows delivery anyway. Enable the checklist requirement if approval is mandatory.`;
      preview.hidden=!enabled;
      preview.classList.toggle('needs-correction',!!review.issue);
      preview.innerHTML=enabled?`<span class="eyebrow">BEFORE YOU CONFIRM · ${review.records.length} PROJECTS</span>${review.issue?`<p class="rule-issue">${e(review.issue)}</p><button class="button small" type="button" id="contextual-followup">Use reusable task template</button>`:''}<ul class="followup-examples">${examples.map(page=>`<li><strong>${e(page.title)}</strong><p>${e(ExitForge.followupText(template,page))}</p></li>`).join('')}</ul>${review.records.length>examples.length?`<small>Showing ${examples.length} of ${review.records.length} records.</small>`:''}<small>Preview only. Created after delivery under your confirmed rule. Existing tasks are kept.</small>`:'';
      document.getElementById('contextual-followup')?.addEventListener('click',()=>{
        document.getElementById('followup-text').value=review.client_count?'Confirm {client} received {project}.':'Review the next step for {project}.';
        document.getElementById('confirm-rule').checked=false;saveReview();
        message('Reusable template selected by you. The original Meta proposal is preserved. Review the examples, then confirm.');
      });
      const decision=document.getElementById('decision-rule');
      if(decision){
        decision.textContent=(rule.field||'No field')+' → '+(rule.delivery_state||'No delivery');
        document.getElementById('decision-difference').textContent=review.issue?'Correction required before activation.':
          template===project.ai_review.specification.followup?'Proposal wording retained; explicit approval still required.':'Follow-up wording edited by you. Original proposal retained.';
      }
    }
    updateFollowupPreview();
    function saveReview(){
      updateFollowupPreview();
      reviewDraft={name:document.getElementById('workspace-name').value,field:document.getElementById('status-field').value,
        states:document.getElementById('workflow-states').value,delivery:document.getElementById('delivery-state').value,
        followup:document.getElementById('followup-text').value,requireChecklist:document.getElementById('require-checklist').checked,
        acceptRelations:document.getElementById('accept-relations')?.checked||false};
      renderNav();clearTimeout(draftTimer);draftTimer=setTimeout(persistDraft,200);
    }
    for(const id of ['workspace-name','status-field','workflow-states','delivery-state','followup-text','require-checklist','accept-relations']){
      const field=document.getElementById(id);field?.addEventListener('input',saveReview);field?.addEventListener('change',saveReview);
    }
  }
  function updateDelivery(values){
    const element=document.getElementById('delivery-state'),previous=element.value;
    element.innerHTML='<option value="">No delivery automation</option>'+values.map(s=>`<option ${s===previous?'selected':''}>${e(s)}</option>`).join('');
  }
  async function runAI(){
    if(busy)return;
    if(!document.getElementById('cloud-consent').checked){message('Confirm the cloud-data operation before using the AI providers.',true);return;}
    const route=document.getElementById('ai-route').value;
    document.getElementById('cloud-consent').checked=false;
    busy=true;loading(providerStatus?.deployment?.mode==='public-demo'?'Meta is reading your source through Baseten. Keep this tab open; no automatic retry will be made…':route==='baseten'?'Interpreting source evidence with Meta open weights via Baseten, then configuring the view…':'Interpreting source evidence with Meta API, ranking templates and configuring the view…');
    document.getElementById('run-ai').disabled=true;
    try{
      const result=await (await request('/api/enhance',{project,consent:true,screenshot,route})).json();
      project.ai_review=result;if(result.presentation)project.presentation=result.presentation;
      project.name=result.specification.workspace_name||project.name;
      project.workflow={field:result.specification.status_field,states:result.specification.states,
        delivery_state:result.specification.delivery_state,followup:result.specification.followup,
        require_checklist:result.specification.require_checklist,confirmed:false,basis:'Model proposal; requires user confirmation'};
      project.provenance.cloud_calls.push(...result.calls);reviewDraft=null;busy=false;renderReview();renderNav();persistDraft();message(result.outcome==='partial'?'Interpretation saved. AI setup is incomplete; continue manual review without another call.':'AI proposal received. Inspect the evidence gaps and confirm the proposed rules before activation.');
    }catch(error){busy=false;document.getElementById('run-ai').disabled=false;renderHostedAI();message(error.message,true);}
  }
  function renderWorkspace(){
    screen.innerHTML=intro('YOUR DATA. A WORKING APPLICATION.',project.process?'Keep the work moving.':isHandoff()?'Finish the Northstar handoff.':demo?'Your recovered workspace.':'Pick up where<br>you left off.',project.process?'Approve linked items, request changes and hand over only when the reviewed process permits it.':'Open a project, finish its checklist and move it to delivery. Your confirmed rule will create the local follow-up task.',`<button class="button primary" id="continue-export">Take it with you ${icon('arrow')}</button>`)+demoGuide()+`<div id="workspace-preview"></div>`;
    controller=ExitForge.mount(document.getElementById('workspace-preview'),project,{portable:false,
      onChange:next=>{project=next;updateDemo();return persistDraft().ok;},
      onBlockedTransition:event=>{if(demo&&event.pageId===demo.pageId&&event.target===project.workflow.delivery_state){demo.guard=true;updateDemo();}}
    });
    updateDemo();
    document.getElementById('continue-export').onclick=()=>go(3);
  }
  function renderExport(){
    screen.innerHTML=intro('KEEP YOUR NEXT CHAPTER.','Your work.<br>No strings attached.','Download a working application with your current data, confirmed rules and local files. Keep using it after the original service and this studio are closed.')+
      demoGuide()+`<div class="export-layout"><section class="panel"><div class="export-visual"><span class="eyebrow">INDEPENDENT APPLICATION</span><div><h2>${e(project.name)}</h2><p>${project.pages.length} pages. ${project.tasks.length} follow-up task${project.tasks.length===1?'':'s'}. One application you control.</p></div><div class="button-row"><span class="pill local">${icon('check')} Offline-ready runtime</span><span class="pill">HTML / no install</span></div></div><div class="export-details"><div class="export-detail">${icon('check')}<div><strong>Keep working without a connection</strong><p>Open the downloaded file in a desktop Chromium browser. Edits are saved on that device.</p></div></div><div class="export-detail">${icon('file')}<div><strong>The data and runtime travel together</strong><p>Pages, safe local attachments and the application source are included. No API keys are included.</p></div></div><div class="export-detail">${icon('download')}<div><strong>You can leave ExitForge too</strong><p>Download a current data backup or another application copy from inside your independent workspace.</p></div></div></div><div class="button-row"><button class="button primary" id="download-local">Download independent app ${icon('download')}</button><button class="button" id="download-data">Data backup</button><button class="button small" id="export-receipt">Recovery receipt</button></div><p class="review-footer">The file contains your workspace data. Store it like any other private project file. Browser storage can be cleared; keep regular data backups.</p></section><div><section class="panel"><h2>The disconnect moment.</h2><p>Try the complete offline journey.</p><ol class="offline-instructions"><li>Save the application file, then open it in your browser.</li><li>Disconnect the network. The application already contains its runtime and data.</li><li>${project.process?'Approve linked items and hand over their project. Inspect the local receipt.':'Finish a checklist and deliver a project. Open the new follow-up task.'}</li><li>Reload. Your changes should remain on this device. Download a fresh backup.</li></ol><button class="button small" id="back-workspace">Back to workspace ${icon('arrow')}</button></section><section class="panel" style="margin-top:20px"><h2>Package with Modal</h2><p>Use the same compiler in isolated cloud compute. Requires a deployed worker, credentials and explicit cloud-use authorization.</p><label class="checkbox-row"><input id="modal-consent" type="checkbox"><span>Send this workspace, including attachments, to Modal for this packaging operation.</span></label><button class="button small" id="download-modal">Build with Modal ${icon('download')}</button><p class="review-footer">Local packaging above runs without cloud access. An untested provider connection is not reported as verified.</p></section></div></div>`;
    updateDemo();
    document.getElementById('download-data').onclick=()=>download(new Blob([JSON.stringify(project,null,2)],{type:'application/json'}),filename(project.name)+'.json');
    document.getElementById('download-local').onclick=()=>packageApp(false);
    document.getElementById('download-modal').onclick=()=>packageApp(true);
    document.getElementById('export-receipt').onclick=downloadReceipt;
    document.getElementById('back-workspace').onclick=()=>go(2);
  }
  async function packageApp(modal){
    if(busy)return;
    if(modal&&!document.getElementById('modal-consent').checked){message('Confirm the Modal data operation first.',true);return;}
    busy=true;loading(modal?'Packaging with the configured Modal worker…':'Packaging the application and its current workspace data locally…');
    try{
      const start=performance.now();
      const response=await request(modal?'/api/modal-package':'/api/package',{project,consent:modal});
      const blob=await response.blob();
      const name=filename(project.name)+'.html';
      download(blob,name);
      document.getElementById('package-receipt')?.remove();
      const receipt=document.createElement('section');receipt.id='package-receipt';receipt.className='package-receipt';
      receipt.setAttribute('role','status');receipt.setAttribute('aria-label','Application download');
      receipt.innerHTML=`<span class="receipt-mark">${icon('download')}</span><div><span class="eyebrow">APPLICATION PACKAGED ${modal?'WITH MODAL':'LOCALLY'}</span><h2>${e(name)}</h2><p>${(blob.size/1024).toFixed(1)} KB · ${project.pages.length} pages · ${project.tasks.length} follow-up task${project.tasks.length===1?'':'s'}</p><strong>Open the file. Disconnect. Keep working.</strong><p>This confirms packaging and a download request. Check the saved file in your browser; offline operation is not observed by this studio.</p></div>`;
      document.querySelector('.export-layout').before(receipt);
      receipt.scrollIntoView({block:'center',behavior:'instant'});
      if(modal)project.provenance.cloud_calls.push({provider:'Modal',operation:'package',elapsed_ms:Math.round(performance.now()-start)});
      message(`Application packaged ${modal?'with Modal':'locally'} in ${((performance.now()-start)/1000).toFixed(2)} s. Open the downloaded HTML file to test offline operation.`);
    }catch(error){message(error.message,true);}finally{busy=false;}
  }
  async function showConnections(){
    const dialog=document.querySelector('.integration-dialog');
    try{providerStatus=await (await fetch('/api/status')).json();}
    catch(_){message('The local server is not available.',true);return;}
    dialog.innerHTML=`<div class="dialog-top"><span class="eyebrow">PROVIDER CONNECTIONS</span><button class="icon-button" data-close aria-label="Close connections">${icon('close')}</button></div><h2>Clear about what is connected.</h2><p>${providerStatus.deployment?.mode==='public-demo'?e(providerStatus.deployment.notice):'Credentials stay on the application server. No key values are returned to this screen.'}</p><span class="pill ${providerStatus.cloud_enabled?'local':'warn'}">Cloud operations ${providerStatus.cloud_enabled?'enabled':'disabled'}</span><div class="provider-list">${providerStatus.providers.map(p=>`<div class="provider-row"><div><strong>${e(p.name)}</strong><p>${e(p.role)}</p>${providerStatus.deployment?.mode==='public-demo'?'':`<code>${e(p.setting)}</code>`}</div><span class="pill ${p.configured?'local':'warn'}">${p.configured?'Credentials configured':'Not configured'}</span></div>`).join('')}</div><p class="review-footer">${providerStatus.deployment?.mode==='public-demo'?'ZIP import and app packaging are processed by this VPS. Browser drafts stay on this device. Meta via Baseten requires consent and limited trial allowance. You do not need a provider account or API key.':'Configure app/.env locally using .env.example. Enabling cloud operations may incur provider charges. Configured reports credential presence, not a successful request. The current workspace proposal records attempted calls and identifies incomplete stages.'}</p><button class="button" data-done>Done</button>`;
    dialog.querySelector('[data-close]').onclick=()=>dialog.close();dialog.querySelector('[data-done]').onclick=()=>dialog.close();
    if(!dialog.open)dialog.showModal();
  }
  document.querySelectorAll('[data-integrations]').forEach(button=>button.onclick=showConnections);
  document.getElementById('header-import').onclick=()=>{
    if(busy)return;
    go(0);document.getElementById('hero-import').click();
  };
  renderNav();renderImport();refreshHostedAI();
})();
