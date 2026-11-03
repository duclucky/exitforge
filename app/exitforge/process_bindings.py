"""Source-owned relation coverage; the model selects semantics, not row identities."""
import copy
import hashlib
import json

MODEL_FIELDS={'version','name','binding_id','parent_field','child_field','actions','evidence_sources','unknowns'}
LEGACY_FIELDS=(MODEL_FIELDS-{'binding_id'})|{'parent_db','child_db','parent_states','child_states','links'}


def source_bindings(project):
    """Return only database pairs with one explicit parent for every child row."""
    pages={page['id']:page for page in project['pages']}
    candidates=[]
    for parent in project['databases']:
        parent_rows=set(parent['rows'])
        if not parent_rows:continue
        for child in project['databases']:
            if child['id']==parent['id'] or not child['rows'] or parent_rows.intersection(child['rows']):continue
            links=[]
            for row in child['rows']:
                page=pages[row]
                targets={link['target'] for link in page['links'] if not link['external']}
                targets|={relation['target'] for relation in page['relations'] if relation['confirmed']}
                matches=targets&parent_rows
                if len(matches)!=1:break
                links.append({'child':row,'parent':next(iter(matches))})
            else:
                identity=hashlib.sha256((parent['id']+':'+child['id']).encode()).hexdigest()[:16]
                candidates.append({'id':'binding-'+identity,'parent_db':parent['id'],'child_db':child['id'],
                                   'parent_title':parent['title'],'child_title':child['title'],'links':links})
    return sorted(candidates,key=lambda candidate:candidate['id'])


def assemble_process(project, proposal, candidates):
    """Hydrate a compact proposal, or a consistent legacy subset, from source facts."""
    if not isinstance(proposal,dict):raise ValueError('The model proposal must be a JSON object.')
    keys=set(proposal)
    if keys==MODEL_FIELDS:
        selected=next((item for item in candidates if item['id']==proposal['binding_id']),None)
        if not selected:raise ValueError('The model selected an unsupported source binding.')
        process={key:copy.deepcopy(value) for key,value in proposal.items() if key!='binding_id'}
        provided=None
    elif keys==LEGACY_FIELDS:
        selected=next((item for item in candidates if item['parent_db']==proposal['parent_db'] and item['child_db']==proposal['child_db']),None)
        if not selected:raise ValueError('The selected databases do not have a complete unambiguous source binding.')
        process=copy.deepcopy(proposal)
        supplied=proposal['links']
        if not isinstance(supplied,list) or len(supplied)>1000:raise ValueError('Invalid model relation list.')
        canonical={link['child']:link['parent'] for link in selected['links']};seen=set()
        for link in supplied:
            if (not isinstance(link,dict) or set(link)!={'child','parent'}
                or not isinstance(link['child'],str) or not isinstance(link['parent'],str)
                or link['child'] in seen or canonical.get(link['child'])!=link['parent']):
                raise ValueError('Model relations contradict or duplicate explicit source evidence.')
            seen.add(link['child'])
        provided=len(supplied)
    else:
        raise ValueError('The model returned unsupported process fields.')
    process.update(parent_db=selected['parent_db'],child_db=selected['child_db'],links=copy.deepcopy(selected['links']))
    if keys==MODEL_FIELDS:
        pages={page['id']:page for page in project['pages']};databases={db['id']:db for db in project['databases']}
        for role in ('parent','child'):
            field=process[role+'_field'];db=databases[process[role+'_db']]
            if not isinstance(field,str) or field not in db['fields']:raise ValueError('The model selected a field absent from its source database.')
            values=[pages[row]['properties'].get(field) for row in db['rows']]
            process[role+'_states']=list(dict.fromkeys(value for value in values if value not in (None,'')))
    pairs=sorted((item['child'],item['parent']) for item in selected['links'])
    resolution={'method':'explicit_source_links','binding_id':selected['id'],'relationship_count':len(pairs),
                'graph_sha256':hashlib.sha256(json.dumps(pairs,separators=(',',':')).encode()).hexdigest(),
                'model_supplied_link_count':provided,
                'completed_omitted_links':0 if provided is None else len(pairs)-provided}
    return process,resolution
