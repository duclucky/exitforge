"""Original synthetic linked-workflow exports; no customer or vendor workspace."""
import csv
import hashlib
import io
import json
import zipfile
from .importer import recover_archive


def process_case(domain='delivery'):
    if domain=='delivery':
        labels={'parent_title':'Projects','child_title':'Deliverables','parent_field':'Project phase','child_field':'Review outcome',
          'parent_states':['In progress','Changes requested','Delivered'],'child_states':['Draft','Changes requested','Approved'],
          'parents':['Brand launch','Website refresh','Reference project'],'children':['Logo pack','Usage guide','Homepage','Reference assets']}
    elif domain=='editorial':
        labels={'parent_title':'Editions','child_title':'Articles','parent_field':'Publication step','child_field':'Sign-off',
          'parent_states':['Assembling','Revision','Released'],'child_states':['Writing','Amend','Accepted'],
          'parents':['Autumn issue','Winter issue','Archive edition'],'children':['Feature article','Cover copy','Winter report','Archive article']}
    else:raise ValueError('Unknown linked-workflow fixture.')
    def uid(value):return hashlib.sha256((domain+value).encode()).hexdigest()[:32]
    parent_db=uid('parent-db');child_db=uid('child-db')
    parent_ids=[uid(name) for name in labels['parents']];child_ids=[uid(name) for name in labels['children']]
    parent_folder=f"{labels['parent_title']} {parent_db}";child_folder=f"{labels['child_title']} {child_db}"
    parent_rows=io.StringIO();pw=csv.writer(parent_rows,lineterminator='\n');pw.writerow(['Name',labels['parent_field'],'Client'])
    child_rows=io.StringIO();cw=csv.writer(child_rows,lineterminator='\n');cw.writerow(['Name',labels['child_field'],'Project'])
    parent_indexes=[0,0,1,2];parent_state_indexes=[0,1,2];child_state_indexes=[0,2,1,2]
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as archive:
        def write(path,body):archive.writestr(zipfile.ZipInfo(path,(2026,10,27,0,0,0)),body)
        for index,(title,page_id) in enumerate(zip(labels['parents'],parent_ids)):
            pw.writerow([title,labels['parent_states'][parent_state_indexes[index]],['Northstar Studio','Cedar & Co','Lumen Collective'][index]])
            write(f'{parent_folder}/{title} {page_id}.md',f'# {title}\n\nAuthorized synthetic working record.\n\n[Handoff note](../handoff-note.txt)\n')
        for index,(title,page_id) in enumerate(zip(labels['children'],child_ids)):
            parent_index=parent_indexes[index];parent_title=labels['parents'][parent_index]
            cw.writerow([title,labels['child_states'][child_state_indexes[index]],parent_title])
            write(f'{child_folder}/{title} {page_id}.md',f'# {title}\n\n[Parent project](../{parent_folder}/{parent_title} {parent_ids[parent_index]}.md)\n\nOriginal synthetic deliverable for workflow reconstruction.\n')
        write(parent_folder+'.csv',parent_rows.getvalue());write(child_folder+'.csv',child_rows.getvalue())
        write('handoff-note.txt','Purpose-created handoff context. Production artwork is not included.\n')
        write('Continuity note.md','# Continuity note\n\nThis is a fictional workspace. The screenshots show selected actions, not all original automations. External notifications, permissions and behavior for projects without items are not established by the export.\n')
    project=recover_archive(stream.getvalue(),f'{domain}-linked-workspace.zip')
    project['name']='Northstar delivery desk' if domain=='delivery' else 'Independent publication desk'
    project['provenance'].update(sample=True,scenario='linked-'+domain)
    expected={'version':1,'name':project['name'],'parent_db':parent_db,'child_db':child_db,
      'parent_field':labels['parent_field'],'child_field':labels['child_field'],
      'parent_states':labels['parent_states'],'child_states':labels['child_states'],
      'links':[{'child':child_ids[i],'parent':parent_ids[parent_indexes[i]]} for i in range(4)],
      'actions':[
        {'id':'approve','kind':'approve_child','label':'Approve item','to':labels['child_states'][2],'evidence_sources':['frame-3.png']},
        {'id':'revise','kind':'request_changes','label':'Request changes','to':labels['child_states'][1],'parent_to':labels['parent_states'][1],'evidence_sources':['frame-2.png']},
        {'id':'handover','kind':'handover_parent','label':'Hand over','to':labels['parent_states'][2],'approved_state':labels['child_states'][2],'task':'Confirm {client} received {project}.','evidence_sources':['frame-1.png','frame-4.png']}],
      'evidence_sources':['frame-1.png','frame-2.png','frame-3.png','frame-4.png'],
      'unknowns':['Original permissions and external notifications are unknown.']}
    return project,expected,stream.getvalue(),labels


def source_demo_html(project,expected,labels):
    """Actual tiny source fixture with visible state changes, not generated output."""
    packet=json.dumps({'project':project,'expected':expected,'labels':labels}).replace('<','\\u003c')
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><title>Synthetic source workspace</title>
<style>body{font:17px/1.5 Arial;margin:28px;color:#18253c;background:#f4f7fc}header{border-bottom:3px solid #234ea3;margin-bottom:18px}small{font-size:12px;color:#345}h1{margin:5px 0}section{background:white;padding:18px;margin:12px 0;border:1px solid #bac7de}table{width:100%;border-collapse:collapse}td,th{text-align:left;border-bottom:1px solid #ddd;padding:10px}button{padding:9px 12px;margin:4px;background:#244b9b;color:white;border:0;font-size:14px}#message{padding:14px;background:#fff0bc;border:2px solid #a96d00;min-height:26px}.state{font-weight:bold;color:#234ea3}</style>
<header><small>FICTIONAL SOURCE WORKSPACE · PURPOSE-CREATED DEMO</small><h1 id="name"></h1><p>Original data and selected workflow observations</p></header><div id="message">Choose an action.</div><section id="parent"></section><section id="children"></section><div id="tasks"></div>
<script>const input='''+packet+''';const data=input.project,cfg=input.expected,labels=input.labels;
const first=data.pages.find(p=>p.id===cfg.links[0].parent);let tasks=0;
function render(){document.querySelector('#name').textContent=data.name;
 document.querySelector('#parent').innerHTML='<h2>'+labels.parent_title+': '+first.title+'</h2><p>'+cfg.parent_field+': <span class="state">'+first.properties[cfg.parent_field]+'</span></p><button id="handover">Hand over</button>';
 const children=cfg.links.filter(l=>l.parent===first.id).map(l=>data.pages.find(p=>p.id===l.child));
 document.querySelector('#children').innerHTML='<h2>'+labels.child_title+'</h2><table><tr><th>Item</th><th>'+cfg.child_field+'</th><th>Actions</th></tr>'+children.map((p,i)=>'<tr><td>'+p.title+'</td><td class="state">'+p.properties[cfg.child_field]+'</td><td><button data-approve="'+p.id+'">Approve '+p.title+'</button><button data-revise="'+p.id+'">Request changes '+p.title+'</button></td></tr>').join('')+'</table>';
 document.querySelector('#tasks').textContent='Local receipt tasks: '+tasks;
 document.querySelector('#handover').onclick=()=>{const pending=children.filter(p=>p.properties[cfg.child_field]!==cfg.actions[2].approved_state);if(pending.length){document.querySelector('#message').textContent='Hand over blocked: '+pending.map(p=>p.title).join(', ')+' must be '+cfg.actions[2].approved_state+'.';return;}first.properties[cfg.parent_field]=cfg.actions[2].to;tasks=1;render();document.querySelector('#message').textContent='Hand over complete. One local receipt task created.';};
 document.querySelectorAll('[data-approve]').forEach(b=>b.onclick=()=>{const p=data.pages.find(p=>p.id===b.dataset.approve);p.properties[cfg.child_field]=cfg.actions[0].to;render();document.querySelector('#message').textContent='Approved '+p.title+'.';});
 document.querySelectorAll('[data-revise]').forEach(b=>b.onclick=()=>{const p=data.pages.find(p=>p.id===b.dataset.revise);p.properties[cfg.child_field]=cfg.actions[1].to;first.properties[cfg.parent_field]=cfg.actions[1].parent_to;render();document.querySelector('#message').textContent='Changes requested for '+p.title+'. Parent moved to '+cfg.actions[1].parent_to+'.';});
}render();</script></html>'''
