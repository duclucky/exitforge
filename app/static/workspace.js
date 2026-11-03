/* Workspace boundaries shared by studio drafts and portable backups. */
(function (global) {
  'use strict';
  const record = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const text = value => typeof value === 'string';
  const strings = value => Array.isArray(value) && value.every(text);
  function requireValue(condition, label) {
    if (!condition) throw new Error(`The backup contains invalid ${label}.`);
  }
  function validateWorkspace(data, expectedId) {
    requireValue(record(data) && data.schema_version === 1 && text(data.id) && text(data.name), 'workspace identity');
    if (expectedId !== undefined && data.id !== expectedId) throw new Error('Choose a data backup for this workspace.');
    requireValue(Array.isArray(data.pages) && data.pages.length > 0 && data.pages.length <= 1000, 'pages');
    const ids = new Set();
    for (const page of data.pages) {
      requireValue(record(page) && ['id','title','body','source'].every(key=>text(page[key])) && !ids.has(page.id), 'page identity');
      ids.add(page.id);
      if(page.local_record!==undefined){
        const origin=page.local_record,stamp=origin?.created_at;
        requireValue(record(origin)&&Object.keys(origin).length===1&&text(stamp)&&Number.isFinite(Date.parse(stamp))&&new Date(stamp).toISOString()===stamp&&page.id.trim()===page.id&&/^local-[A-Za-z0-9_-]{1,80}$/.test(page.id)&&page.source==='ExitForge-created/'+page.id+'.md','local record origin');
      }
      requireValue(record(page.properties) && Object.values(page.properties).every(text), 'record properties');
      requireValue(['links','relations','attachments','checklist'].every(key=>Array.isArray(page[key])), 'page collections');
      requireValue(page.checklist.every(item=>record(item) && text(item.text) && typeof item.done === 'boolean'), 'checklists');
      requireValue(page.links.every(link=>record(link) && text(link.href) && text(link.label) && typeof link.external === 'boolean' && (link.target === null || text(link.target))), 'page links');
      requireValue(page.relations.every(link=>record(link) && text(link.field) && text(link.target) && typeof link.confirmed === 'boolean'), 'relations');
      requireValue(strings(page.attachments), 'attachment references');
    }
    requireValue(record(data.assets) && Array.isArray(data.databases), 'assets or databases');
    const types = {'.txt':'text/plain','.pdf':'application/pdf','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.webp':'image/webp','.gif':'image/gif'};
    let assetBytes = 0;
    for (const asset of Object.values(data.assets)) {
      requireValue(record(asset) && text(asset.name) && text(asset.data) && !/[\\/:]/.test(asset.name), 'attachment filename');
      const extension = asset.name.slice(asset.name.lastIndexOf('.')).toLowerCase();
      requireValue(Object.hasOwn(types,extension) && asset.mime === types[extension], 'attachment type');
      requireValue(asset.data.length % 4 === 0 && /^[A-Za-z0-9+/]*={0,2}$/.test(asset.data), 'attachment encoding');
      try { assetBytes += atob(asset.data).length; } catch (_) { throw new Error('The backup contains invalid attachment encoding.'); }
    }
    requireValue(assetBytes <= 3 * 1024 * 1024, 'attachment size (3 MB maximum)');
    for (const page of data.pages) {
      requireValue(page.links.every(link=>link.target === null || ids.has(link.target)) && page.relations.every(link=>ids.has(link.target)), 'page references');
      requireValue(page.attachments.every(key=>Object.hasOwn(data.assets,key)), 'attachment references');
    }
    const databases = new Set();
    for (const database of data.databases) {
      requireValue(record(database) && text(database.id) && !databases.has(database.id) && strings(database.fields) && strings(database.rows) && database.rows.every(id=>ids.has(id)), 'database references');
      databases.add(database.id);
    }
    const rule = data.workflow;
    requireValue(record(rule) && ['field','delivery_state','followup'].every(key=>text(rule[key])) && strings(rule.states) && rule.states.length <= 8 && new Set(rule.states).size === rule.states.length && rule.states.every(state=>state.length <= 100), 'workflow');
    requireValue(typeof rule.confirmed === 'boolean' && typeof rule.require_checklist === 'boolean', 'workflow approval');
    requireValue(Array.isArray(data.tasks) && Array.isArray(data.activity) && strings(data.warnings) && record(data.provenance), 'workspace history');
    requireValue(data.provenance.cloud_calls === undefined || Array.isArray(data.provenance.cloud_calls), 'cloud call history');
    const taskIds = new Set();
    for (const task of data.tasks) {
      requireValue(record(task) && ['id','page','text'].every(key=>text(task[key])) && ids.has(task.page) && typeof task.done === 'boolean' && !taskIds.has(task.id), 'follow-up tasks');
      taskIds.add(task.id);
    }
    requireValue(data.activity.every(event=>record(event) && text(event.text) && text(event.at)), 'activity history');
    if (data.presentation !== undefined) {
      requireValue(record(data.presentation) && ['board','docs'].includes(data.presentation.primary_view), 'view configuration');
      const selected = data.presentation.database_id;
      requireValue(selected === undefined || selected === '' || databases.has(selected), 'selected database');
    }
    if (data.ai_review !== undefined) {
      const proposal = data.ai_review;
      requireValue(record(proposal) && record(proposal.specification) && text(proposal.specification.rationale) && strings(proposal.specification.unknowns) && Array.isArray(proposal.calls), 'AI review');
      requireValue(proposal.calls.every(call=>record(call) && text(call.provider) && Number.isFinite(call.elapsed_ms)), 'AI call history');
    }
    if(data.process!==undefined){
      const engine=typeof module!=='undefined'&&module.exports?require('./process.js'):global.ExitForgeProcess;
      engine.validate(data);
    }
    if(data.process_review!==undefined){
      const r=data.process_review;
      requireValue(data.process&&record(r)&&record(r.proposal)&&Array.isArray(r.calls)&&Array.isArray(r.observations)&&r.observations.length<=6,'process review history');
      requireValue(r.calls.every(call=>record(call)&&text(call.provider)&&Number.isFinite(call.elapsed_ms)),'process call history');
      requireValue(r.observations.every(item=>record(item)&&text(item.id)&&text(item.sha256)&&item.sha256.length===64),'process observation history');
    }
    requireValue(new TextEncoder().encode(JSON.stringify(data)).length <= 12 * 1024 * 1024, 'workspace size (12 MB maximum)');
    return data;
  }
  function boardGroups(data, pages) {
    if (!data.workflow.field || !data.workflow.states.length) return [{state:'Recovered',pages}];
    const states = data.workflow.states;
    const groups = states.map(state=>({state,pages:pages.filter(page=>page.properties[data.workflow.field] === state)}));
    const other = pages.filter(page=>!states.includes(page.properties[data.workflow.field]));
    if (other.length) groups.push({state:'Other / unassigned',pages:other});
    return groups;
  }
  const DRAFT_KEY = 'exitforge.studio.draft.v1';
  function normalizeDraft(input) {
    requireValue(record(input) && Number.isInteger(input.step) && input.step >= 0 && input.step <= 3, 'draft stage');
    validateWorkspace(input.project);
    const draft = {version:1,project:input.project,step:input.step,saved_at:new Date().toISOString()};
    if (input.review !== undefined && input.review !== null) {
      requireValue(record(input.review), 'review draft');
      draft.review = {};
      for (const key of ['name','field','states','delivery','followup']) {
        requireValue(text(input.review[key]) && input.review[key].length <= 1600, 'review draft fields');
        draft.review[key] = input.review[key];
      }
      for (const key of ['requireChecklist','acceptRelations']) {
        requireValue(typeof input.review[key] === 'boolean', 'review draft choices');
        draft.review[key] = input.review[key];
      }
      draft.step = 1;
    }
    if (draft.step > 1 && !(draft.project.process?draft.project.process.confirmed:draft.project.workflow.confirmed)) draft.step = 1;
    return draft;
  }
  class DraftStore {
    constructor(storage) { this.storage = storage; }
    save(input) {
      try {
        const draft = normalizeDraft(input);
        this.storage.setItem(DRAFT_KEY,JSON.stringify(draft));
        return {ok:true,error:'',saved_at:draft.saved_at};
      } catch (_) { return {ok:false,error:'Draft not saved on this device. Download a data backup before closing.'}; }
    }
    load() {
      try {
        const raw = this.storage.getItem(DRAFT_KEY);
        if (!raw) return {draft:null,error:''};
        const parsed = JSON.parse(raw);
        requireValue(parsed.version === 1, 'draft version');
        const draft = normalizeDraft(parsed);
        draft.saved_at = text(parsed.saved_at) ? parsed.saved_at : draft.saved_at;
        return {draft,error:''};
      } catch (_) { return {draft:null,error:'Saved draft could not be read. Import a backup or remove the saved draft.'}; }
    }
    clear() {
      try { this.storage.removeItem(DRAFT_KEY); return {ok:true,error:''}; }
      catch (_) { return {ok:false,error:'The saved draft could not be removed from this browser.'}; }
    }
  }
  function followupReview(data, rule = data.workflow) {
    const records = data.pages.filter(page=>rule.field && Object.hasOwn(page.properties,rule.field));
    const clients = new Set(records.map(page=>page.properties.Client?.trim()||page.properties.Customer?.trim()).filter(Boolean));
    const required = [];
    if (data.ai_review && rule.delivery_state && rule.followup) {
      if (records.length > 1 && !rule.followup.includes('{project}')) required.push('{project}');
      if (clients.size > 1 && !rule.followup.includes('{client}')) required.push('{client}');
    }
    return {records,client_count:clients.size,required,
      issue:required.length?`Make this AI follow-up reusable: include ${required.join(' and ')} or remove the follow-up. The same rule applies to ${records.length} projects.`:''};
  }
  function recoveryReceipt(data) {
    const review = followupReview(data);
    const recovered=data.pages.filter(page=>!page.local_record),created=data.pages.filter(page=>page.local_record);
    return {format:'exitforge-recovery-receipt',version:1,workspace_id:data.id,name:data.name,
      generated_at:new Date().toISOString(),sample:data.provenance.sample===true,
      recovered:{pages:recovered.length,databases:data.databases.length,attachments:Object.keys(data.assets).length,
        parser_workflow:data.provenance.parser_workflow?structuredClone(data.provenance.parser_workflow):null,
        explicit_internal_links:recovered.reduce((n,p)=>n+p.links.filter(link=>link.target).length,0),
        source_paths:[...new Set(recovered.map(p=>p.source))]},
      continued_work:{current_pages:data.pages.length,created_records:created.map(page=>({id:page.id,title:page.title,source:page.source,created_at:page.local_record.created_at})),
        record_activity:structuredClone(data.activity.filter(event=>['create_record','edit_record'].includes(event.operation)))},
      meta_proposal:data.ai_review?{specification:structuredClone(data.ai_review.specification),
        calls:structuredClone(data.ai_review.calls),outcome:data.ai_review.outcome||'complete',
        source:'Recorded operation history; this receipt makes no new inference request.'}:null,
      workflow:structuredClone(data.workflow),review_issues:review.issue?[review.issue]:[],
      linked_process:data.process?{reviewed:structuredClone(data.process),original_proposal:data.process_review?structuredClone(data.process_review):null}:null,
      unresolved:[...data.warnings,...(data.ai_review?.specification.unknowns||[])],
      limits:['Original permissions, formulas and external automations are not recreated.',
        'A completed local task does not mean a message or client delivery was sent.',
        'Human time savings, adoption and general model quality have not been measured.']};
  }
  const api = {validateWorkspace,boardGroups,DraftStore,followupReview,recoveryReceipt};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else global.ExitForgeWorkspace = api;
})(typeof window !== 'undefined' ? window : globalThis);
