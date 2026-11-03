/* Shared, dependency-free runtime for the preview and the independent application. */
(function (global) {
  'use strict';
  const {validateWorkspace,boardGroups,followupReview} = typeof module !== 'undefined' && module.exports ? require('./workspace.js') : global.ExitForgeWorkspace;
  const clone = value => JSON.parse(JSON.stringify(value));
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const icon = name => {
    const paths = {plus:'M12 4v16M4 12h16',arrow:'M5 12h14m-5-5 5 5-5 5',file:'M14 2H6v20h12V6z M14 2v5h5',check:'m5 12 4 4L19 6',link:'M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-2 2M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l2-2',download:'M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5',search:'M21 21l-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',board:'M3 4h18v16H3zM9 4v16m6-16v16',close:'m6 6 12 12M6 18 18 6',task:'M4 4h16v16H4z m4 8 3 3 5-6'};
    return `<svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="${paths[name] || paths.file}"/></svg>`;
  };
  function followupText(template, page) {
    const values={project:page.title,client:page.properties.Client?.trim()||page.properties.Customer?.trim()||'the client'};
    return template.replace(/\{(project|client)\}/g,(_,key)=>values[key]);
  }
  function transition(data, pageId, target) {
    if(data.process)throw new Error('Use the reconstructed process actions; related approvals cannot be bypassed by a status edit.');
    const rule = data.workflow;
    const page = data.pages.find(p => p.id === pageId);
    if (!page || !rule.field || !rule.states.includes(target)) throw new Error('Choose a supported workflow state.');
    const previous = page.properties[rule.field] || '';
    if (previous === target) return data;
    if (rule.confirmed && target === rule.delivery_state) {
      const review = followupReview(data);
      if (review.issue) throw new Error(review.issue+' Review the workflow in the studio.');
    }
    if (rule.confirmed && target === rule.delivery_state && rule.require_checklist && page.checklist.some(c => !c.done)) {
      throw new Error('Complete the handoff checklist before moving this project to delivery.');
    }
    page.properties[rule.field] = target;
    const stamp = new Date().toISOString();
    data.activity.unshift({at:stamp, page:page.id, text:`${page.title}: ${previous || 'Unassigned'} → ${target}`});
    if (rule.confirmed && target === rule.delivery_state && rule.followup && !data.tasks.some(t => t.id === `followup:${page.id}`)) {
      data.tasks.unshift({id:`followup:${page.id}`,page:page.id,text:followupText(rule.followup,page),done:false,created_at:stamp});
    }
    data.activity = data.activity.slice(0, 100);
    return data;
  }
  function mount(root, original, options = {}) {
    if(original.process)return global.ExitForgeProcessUI.mount(root,original,options);
    validateWorkspace(original);
    let data = clone(original), view = original.presentation?.primary_view === 'docs' ? 'docs' : 'board', query = '', selected = null, storageError = '';
    const storageKey = `exitforge.workspace.v1.${data.id}`;
    const toastId = `notice-${Math.random().toString(36).slice(2)}`;
    if (options.portable) {
      try {
        const saved = JSON.parse(localStorage.getItem(storageKey));
        if (saved !== null) data = validateWorkspace(saved,data.id);
      } catch (_) { storageError = 'Saved browser data could not be used. The packaged snapshot is open; keep a data backup before closing this file.'; }
    }
    function notify(text, error = false) {
      const target = root.querySelector('.runtime-notice');
      if (target) { target.textContent = text; target.classList.toggle('error', error); target.hidden = false; }
    }
    function save() {
      try {
        if (options.portable) localStorage.setItem(storageKey, JSON.stringify(data));
        storageError = '';
      } catch (_) { storageError = 'Changes are in memory only: browser storage is full or unavailable. Download a data backup now.'; }
      const draftSaved = options.onChange ? options.onChange(clone(data)) : false;
      const openTasks=root.querySelector('[data-open-tasks]');
      if(openTasks)openTasks.textContent=String(data.tasks.filter(task=>!task.done).length);
      const badge = root.querySelector('[data-save-status]');
      if (badge) badge.textContent = storageError ? 'Backup needed' : options.portable ? 'Saved on this device' : draftSaved ? 'Draft saved on this device' : 'Changes in memory';
      if (storageError) notify(storageError, true);
    }
    function selectedDatabase() {
      return data.databases.find(d => d.id === (data.presentation || {}).database_id) || data.databases[0];
    }
    function matches(...values) {
      return values.join(' ').toLocaleLowerCase().includes(query.trim().toLocaleLowerCase());
    }
    function pageText(page) {
      return page ? `${page.title} ${Object.values(page.properties).join(' ')} ${page.body} ${page.source}` : '';
    }
    function searchSummary(count,label) {
      return query.trim()?`<p class="search-summary" role="status">${count} ${label} matching “${escape(query.trim())}”</p>`:'';
    }
    function noMatches(label) {
      return `<div class="empty-state search-empty"><h3>No matches in ${label}.</h3><p>Try a project name, client or a word from your records.</p><button class="button small" data-reset-search>Show all ${label}</button></div>`;
    }
    function filteredPages() {
      const database = selectedDatabase();
      const ids = new Set(database ? database.rows : data.pages.map(p => p.id));
      return data.pages.filter(p => ids.has(p.id) && matches(pageText(p)));
    }
    function stateClass(state) {
      const index = data.workflow.states.indexOf(state);
      return `state-${Math.max(index,0) % 5}`;
    }
    function card(page) {
      const status = page.properties[data.workflow.field] || 'Unassigned';
      const client = page.properties.Client || page.properties.Customer || '';
      const due = page.properties['Due date'] || page.properties.Due || '';
      const complete = page.checklist.filter(c => c.done).length;
      return `<button class="project-card" data-page="${escape(page.id)}"><span class="card-client">${escape(client || 'Recovered project')}</span><strong>${escape(page.title)}</strong><span class="card-summary">${page.body ? escape(page.body.split('\n').find(x => x && !x.startsWith('#')) || 'Open project details') : 'Open project details'}</span><span class="card-bottom"><span>${page.checklist.length ? icon('check') + ` ${complete}/${page.checklist.length}` : icon('file') + ' Source record'}</span><span>${escape(due)}</span></span><span class="sr-only">${escape(status)}</span></button>`;
    }
    function board() {
      const pages = filteredPages();
      if(!pages.length&&query.trim())return searchSummary(0,'projects')+noMatches('projects');
      const groups = boardGroups(data,pages);
      return searchSummary(pages.length,'projects')+`<div class="board-columns" style="--column-count:${groups.length}">${groups.map(({state,pages:matches}) => {
        return `<section class="board-column"><div class="column-heading"><h3><span class="state-dot ${stateClass(state)}"></span>${escape(state)}</h3><span>${matches.length}</span></div><div class="card-stack">${matches.map(card).join('') || '<p class="empty-column">No projects in this stage.</p>'}</div></section>`;
      }).join('')}</div>${!pages.length ? '<p class="empty-state">No matching projects. Try a different search.</p>' : ''}`;
    }
    function docs() {
      const pages = data.pages.filter(p => matches(pageText(p)));
      return searchSummary(pages.length,'documents')+(pages.length?`<div class="document-grid">${pages.map(p=>`<button class="document-card" data-page="${escape(p.id)}">${icon('file')}<span><strong>${escape(p.title)}</strong><small>${escape(p.source)}</small></span>${icon('arrow')}</button>`).join('')}</div>`:noMatches('documents'));
    }
    function tasks() {
      const filtered=data.tasks.filter(task=>matches(task.text,pageText(data.pages.find(p=>p.id===task.page))));
      if(!filtered.length&&query.trim())return searchSummary(0,'follow-ups')+noMatches('follow-ups');
      return searchSummary(filtered.length,'follow-ups')+`<div class="task-list">${filtered.length ? filtered.map(t => `<label class="task-row"><input type="checkbox" data-task="${escape(t.id)}" ${t.done?'checked':''}><span><strong>${escape(t.text)}</strong><small>${escape(data.pages.find(p=>p.id===t.page)?.title || 'Project')}</small></span></label>`).join('') : `<div class="empty-state">${icon('task')}<h3>A clear handoff, every time.</h3><p>Follow-up tasks appear here when you complete a delivery using your confirmed rule.</p></div>`}</div>`;
    }
    function activity() {
      const filtered=data.activity.filter(event=>matches(event.text,pageText(data.pages.find(p=>p.id===event.page))));
      if(!filtered.length&&query.trim())return searchSummary(0,'activity entries')+noMatches('activity');
      return searchSummary(filtered.length,'activity entries')+`<div class="activity-list">${filtered.length ? filtered.map(a=>`<div class="activity-row"><span class="state-dot"></span><span>${escape(a.text)}</span><time>${escape(new Date(a.at).toLocaleString())}</time></div>`).join('') : '<p class="empty-state">Your local changes will appear here.</p>'}</div>`;
    }
    function render() {
      const database = selectedDatabase();
      const total = database ? database.rows.length : data.pages.length;
      const rowIds = new Set(database ? database.rows : data.pages.map(page=>page.id));
      const finished = data.pages.filter(p => rowIds.has(p.id) && data.workflow.delivery_state && p.properties[data.workflow.field] === data.workflow.delivery_state).length;
      root.innerHTML = `<div class="workspace"><header class="workspace-header"><div><span class="eyebrow">${options.portable?'YOUR INDEPENDENT WORKSPACE':'LIVE WORKSPACE PREVIEW'}</span><h2>${escape(data.name)}</h2><p>${total} project${total===1?'':'s'} · ${data.pages.length} pages · ${Object.keys(data.assets).length} local attachment${Object.keys(data.assets).length===1?'':'s'}</p></div><div class="workspace-tools"><span class="pill local">${icon('check')} Works offline</span>${options.portable?`<button class="button small" data-export-json>${icon('download')} Data backup</button><button class="button small" data-export-app>${icon('download')} Application</button><label class="button small">Restore backup<input type="file" accept=".json" data-restore hidden></label>`:''}</div></header>
        <div class="workspace-overview"><div><span class="mini-label">PROJECTS</span><strong>${total}</strong></div><div><span class="mini-label">DELIVERED</span><strong>${data.workflow.delivery_state ? finished : '—'}</strong></div><div><span class="mini-label">FOLLOW-UPS</span><strong data-open-tasks>${data.tasks.filter(t=>!t.done).length}</strong></div><div class="rule-summary"><span class="mini-label">WORKFLOW</span><span>${!data.workflow.confirmed?'Rules need your confirmation':!data.workflow.delivery_state?'Manual status updates':data.workflow.followup?'Delivery → local follow-up':'Delivery without follow-up'}</span></div></div>
        ${data.databases.length>1?`<label class="database-picker">Database<select data-database aria-label="Active database">${data.databases.map(item=>`<option value="${escape(item.id)}" ${item.id===database?.id?'selected':''}>${escape(item.title||item.id)} (${item.rows.length})</option>`).join('')}</select></label>`:''}
        <div class="workspace-toolbar"><nav class="view-tabs" aria-label="Workspace views">${[['board','board','Projects'],['docs','file','Documents'],['tasks','task','Follow-ups'],['activity','link','Activity']].map(([id,i,label])=>`<button class="view-tab ${view===id?'active':''}" data-view="${id}" aria-current="${view===id?'page':'false'}">${icon(i)}${label}${id==='tasks'&&data.tasks.length?`<span class="tab-count">${data.tasks.length}</span>`:''}</button>`).join('')}</nav><div class="search-control"><label class="search-field">${icon('search')}<input type="search" placeholder="${view==='tasks'?'Find a follow-up or client':view==='activity'?'Find an activity or project':'Find a project or page'}" aria-label="Find a project or page" value="${escape(query)}"></label><button class="icon-button" data-clear-search aria-label="Clear search" ${query?'':'hidden'}>${icon('close')}</button></div></div>
        <div class="runtime-notice ${storageError?'error':''}" role="status" aria-live="polite" id="${toastId}" ${storageError?'':'hidden'}>${escape(storageError)}</div><div class="workspace-content">${view==='board'?board():view==='docs'?docs():view==='tasks'?tasks():activity()}</div>
        <footer class="workspace-footer"><span>${data.provenance.sample?'Purpose-created demo data':'Recovered from your export'} · ${options.portable?'No server, account or AI connection required':'Local recovery preview'}</span><span data-save-status>${storageError?'Backup needed':options.portable?'Saved on this device':'Browser draft available in the studio'}</span></footer><dialog class="page-dialog" aria-label="Project details"></dialog></div>`;
      bind();
    }
    function inline(text, page) {
      const regex = /!?\[([^\]]*)\]\(([^\n)]+)\)/g;
      let result='', start=0, match;
      while ((match=regex.exec(text))) {
        result+=escape(text.slice(start,match.index));
        const link=page.links.find(l=>l.href===match[2]);
        result+=link?.target?`<button class="text-link" data-page="${escape(link.target)}">${escape(match[1])}</button>`:escape(match[1]);
        start=regex.lastIndex;
      }
      return result+escape(text.slice(start));
    }
    function bodyHtml(page) {
      return page.body.split('\n').filter(line=>!/^\s*[-*]\s+\[[ xX]\]/.test(line)).map(line=>{
        if (line.startsWith('# ')) return '';
        if (line.startsWith('## ')) return `<h3>${escape(line.slice(3))}</h3>`;
        if (line.startsWith('### ')) return `<h4>${escape(line.slice(4))}</h4>`;
        return line.trim()?`<p>${inline(line,page)}</p>`:'';
      }).join('');
    }
    function openPage(id, returnFocus) {
      selected=id;
      const page=data.pages.find(p=>p.id===id); if(!page)return;
      const dialog=root.querySelector('dialog');
      const status=page.properties[data.workflow.field];
      let followupOpened=false;
      dialog.innerHTML=`<div class="dialog-top"><span class="eyebrow">RECOVERED PAGE</span><button class="icon-button" data-close aria-label="Close project details">${icon('close')}</button></div><h2>${escape(page.title)}</h2><div class="source-path">${icon('file')}<span>${escape(page.source)}</span></div><div class="property-list">${Object.entries(page.properties).filter(([k])=>!['name','title'].includes(k.toLowerCase())).map(([key,value])=>`<div><span>${escape(key)}</span>${key===data.workflow.field?`<select aria-label="Project status" data-status>${data.workflow.states.map(s=>`<option ${s===status?'selected':''}>${escape(s)}</option>`).join('')}</select>`:`<strong>${escape(value)}</strong>`}</div>`).join('')}</div><div class="dialog-message" role="status" aria-live="polite"></div>${page.checklist.length?`<section class="checklist"><h3>Handoff checklist</h3>${page.checklist.map((c,i)=>`<label><input type="checkbox" data-check="${i}" ${c.done?'checked':''}><span>${escape(c.text)}</span></label>`).join('')}</section>`:''}
        <section class="page-body">${bodyHtml(page)||'<p>No separate Markdown body was available for this record.</p>'}</section>${page.links.some(l=>l.target)||page.relations.some(l=>l.confirmed)?`<section><h3>Connected pages</h3><div class="linked-pages">${page.links.filter(l=>l.target).map(l=>`<button class="button small" data-page="${escape(l.target)}">${icon('link')}${escape(l.label)}</button>`).join('')}${page.relations.filter(l=>l.confirmed).map(l=>`<button class="button small" data-page="${escape(l.target)}">${icon('link')}${escape(l.field)}: ${escape(data.pages.find(p=>p.id===l.target)?.title)}</button>`).join('')}</div></section>`:''}
        ${page.attachments.length?`<section><h3>Local attachments</h3>${page.attachments.map(id=>`<button class="attachment" data-asset="${escape(id)}">${icon('download')}<span>${escape(data.assets[id]?.name)}</span><small>Included in your application</small></button>`).join('')}</section>`:''}<details class="edit-notes"><summary>Edit page notes</summary><label class="field">Page title<input data-title value="${escape(page.title)}"></label><label class="field">Notes (Markdown)<textarea data-body rows="8">${escape(page.body)}</textarea></label><button class="button primary small" data-save-notes>Save notes</button></details>`;
      if(!dialog.open)dialog.showModal();
      dialog.querySelector('[data-close]').onclick=()=>dialog.close();
      dialog.querySelectorAll('[data-page]').forEach(b=>b.onclick=()=>openPage(b.dataset.page));
      dialog.querySelectorAll('[data-check]').forEach(input=>input.onchange=()=>{page.checklist[Number(input.dataset.check)].done=input.checked;save();});
      dialog.querySelector('[data-status]')?.addEventListener('change',e=>{
        const feedback=dialog.querySelector('.dialog-message');
        feedback.classList.remove('error');
        try {
          const hadFollowup=data.tasks.some(task=>task.id===`followup:${page.id}`);
          transition(data,page.id,e.target.value);save();
          const followup=data.tasks.find(task=>task.id===`followup:${page.id}`);
          const delivered=data.workflow.confirmed&&e.target.value===data.workflow.delivery_state;
          feedback.innerHTML=`<strong>Stage updated. ${escape(e.target.value)}.</strong>`;
          if(delivered&&followup){
            feedback.innerHTML+=`<div class="handoff-receipt"><span class="eyebrow">${hadFollowup?'Existing follow-up':'New follow-up'}</span><p>${escape(followup.text)}</p><button class="button small" data-show-followup>View follow-up ${icon('arrow')}</button></div>`;
            feedback.querySelector('[data-show-followup]').onclick=()=>{view='tasks';query='';followupOpened=true;dialog.close();};
          }
          feedback.scrollIntoView({block:'nearest',behavior:'instant'});
        }
        catch(error){
          const target=e.target.value;
          e.target.value=page.properties[data.workflow.field];feedback.classList.add('error');feedback.textContent=error.message;
          feedback.scrollIntoView({block:'nearest',behavior:'instant'});
          options.onBlockedTransition?.({pageId:page.id,target});
        }
      });
      dialog.querySelectorAll('[data-asset]').forEach(b=>b.onclick=()=>downloadAsset(b.dataset.asset));
      dialog.querySelector('[data-save-notes]').onclick=()=>{
        const title=dialog.querySelector('[data-title]').value.trim();
        if(!title){const feedback=dialog.querySelector('.dialog-message');feedback.classList.add('error');feedback.textContent='Enter a page title.';feedback.scrollIntoView({block:'nearest',behavior:'instant'});return;}
        page.title=title;page.body=dialog.querySelector('[data-body]').value;save();openPage(page.id);
        dialog.querySelector('.dialog-message').textContent='Notes saved.';
        dialog.querySelector('.dialog-message').scrollIntoView({block:'nearest',behavior:'instant'});
      };
      dialog.onclose=()=>{
        selected=null;render();
        const target=followupOpened?root.querySelector('[data-view="tasks"]'):returnFocus?.isConnected?returnFocus:
          (returnFocus?.id?document.getElementById(returnFocus.id):null)||
          [...root.querySelectorAll('[data-page]')].find(button=>button.dataset.page===id);
        target?.focus();
      };
      dialog.onclick=e=>{if(e.target===dialog)dialog.close();};
    }
    function downloadAsset(id) {
      const asset=data.assets[id];if(!asset)return;
      const binary=atob(asset.data);const bytes=Uint8Array.from(binary,c=>c.charCodeAt(0));
      download(new Blob([bytes],{type:asset.mime}),asset.name);
    }
    function bindContent() {
      root.querySelectorAll('.workspace-content [data-page]').forEach(b=>b.onclick=()=>openPage(b.dataset.page,b));
      root.querySelectorAll('[data-task]').forEach(c=>c.onchange=()=>{const task=data.tasks.find(t=>t.id===c.dataset.task);task.done=c.checked;save();});
      root.querySelector('[data-reset-search]')?.addEventListener('click',clearSearch);
    }
    function refreshSearch() {
      root.querySelector('.workspace-content').innerHTML=view==='board'?board():view==='docs'?docs():view==='tasks'?tasks():activity();
      root.querySelector('[data-clear-search]').hidden=!query;
      bindContent();
    }
    function clearSearch() {
      query='';const input=root.querySelector('input[type=search]');input.value='';refreshSearch();input.focus();
    }
    function bind() {
      root.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{view=b.dataset.view;render();});
      bindContent();
      const search=root.querySelector('input[type=search]');
      search.oninput=e=>{query=e.target.value;refreshSearch();};
      root.querySelector('[data-clear-search]').onclick=clearSearch;
      root.querySelector('[data-database]')?.addEventListener('change',event=>{
        data.presentation={...(data.presentation||{primary_view:'board'}),database_id:event.target.value};save();render();
      });
      root.querySelector('[data-export-json]')?.addEventListener('click',()=>download(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}),filename(data.name)+'.json'));
      root.querySelector('[data-export-app]')?.addEventListener('click',()=>{
        const page=document.documentElement.cloneNode(true);
        page.querySelector('#workspace-data').textContent=JSON.stringify(data).replace(/</g,'\\u003c').replace(/>/g,'\\u003e').replace(/&/g,'\\u0026');
        page.querySelector('#workspace-main').innerHTML='';
        download(new Blob(['<!doctype html>\n'+page.outerHTML],{type:'text/html'}),filename(data.name)+'.html');
      });
      root.querySelector('[data-restore]')?.addEventListener('change',async e=>{
        try{
          const file=e.target.files[0];if(!file)return;if(file.size>12*1024*1024)throw new Error('Backup exceeds 12 MB.');
          const restored=JSON.parse(await file.text());
          validateWorkspace(restored,data.id);
          const prior=data;data=restored;
          try{render();save();notify('Workspace restored from your data backup.');}catch(error){data=prior;render();throw new Error('The backup contains invalid workspace data.');}
        }catch(error){notify(error.message,true);}
      });
    }
    render();
    return {getWorkspace:()=>clone(data),setWorkspace:next=>{validateWorkspace(next,data.id);data=clone(next);render();},openPage};
  }
  function filename(name){return name.replace(/[^a-zA-Z0-9_-]+/g,'-').replace(/^-|-$/g,'').slice(0,80)||'workspace';}
  function download(blob,name){const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);}
  const api={mount,transition,followupText,escape,icon,download,filename};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  else global.ExitForge=api;
})(typeof window!=='undefined'?window:globalThis);
