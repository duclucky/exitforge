"""Purpose-created, licensed demo fixture; not a real customer's Notion export."""

import csv
import hashlib
import io
import zipfile


def sample_archive(scenario='studio'):
    if scenario=='client-handoff':
        return _client_handoff_archive()
    if scenario!='studio':
        raise ValueError('Unknown sample scenario.')
    output = io.BytesIO()
    db = '1' * 32
    clients = ['Northstar Studio', 'Cedar & Co', 'Lumen Collective']
    statuses = ['In progress', 'Review', 'Delivered']
    rows = io.StringIO()
    writer = csv.writer(rows, lineterminator='\n')
    writer.writerow(['Name', 'Status', 'Client', 'Due date', 'Priority'])
    names = ['Brand launch', 'Spring campaign', 'Website refresh', 'Packaging system', 'Product story',
             'Social toolkit', 'Editorial series', 'Annual report', 'Identity exploration', 'Launch film']
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for i, client in enumerate(clients):
            key = str(i + 7) * 32
            bundle.writestr(f'{client} {key}.md', f'# {client}\n\nClient context, project notes and delivery preferences.\n\nThis is purpose-created sample data.\n')
        for i in range(30):
            title = names[i % len(names)] + (f' / {i // 10 + 1}' if i >= 10 else '')
            key = hashlib.sha256(f'sample-project-{i}'.encode()).hexdigest()[:32]
            folder = f'Projects {db}'
            client = clients[i % 3]
            status = statuses[i % 3]
            writer.writerow([title, status, client, f'2026-11-{i % 9 + 1:02}', 'High' if i % 4 == 0 else 'Normal'])
            client_key = str(i % 3 + 7) * 32
            body = (f'# {title}\n\nA delivery workspace for {client}. Keep the approved brief, the work and the handoff together.\n\n'
                    f'## Project brief\nCreate a clear, useful outcome with a confident visual direction. Keep the original working files in the final delivery.\n\n'
                    f'[Client context](../{client}%20{client_key}.md)\n[Delivery notes](delivery-notes.txt)\n\n'
                    f'## Handoff checklist\n- [x] Confirm the brief\n- [x] Prepare working files\n- [{"x" if status == "Delivered" else " "}] Get final approval\n\n'
                    'Rules are intentionally absent from this export. Declare any automation during review.\n')
            bundle.writestr(f'{folder}/{title.replace("/", "-")} {key}.md', body)
        bundle.writestr(f'Projects {db}.csv', rows.getvalue())
        bundle.writestr(f'Projects {db}/delivery-notes.txt', 'Sample delivery notes\n\nInclude the working files, final exports and a brief handoff summary.\n')
    return output.getvalue()


def _client_handoff_archive():
    """An illustrative exit with remaining work, not a testimonial or outcome study."""
    output=io.BytesIO()
    database='2'*32
    clients=[
        ('Northstar Studio','The client needs an approved logo pack and a concise usage guide. Final approval is still pending.'),
        ('Cedar & Co','The website handoff needs editable source, deployment notes and confirmation of receipt.'),
        ('Lumen Collective','The packaging job has been delivered. Retain the approved print notes for future questions.'),
    ]
    jobs=[
        ('Brand launch','In progress','logo pack and usage guide','Prepare the final logo pack, editable working files and usage guide. The client has not signed off yet.'),
        ('Website refresh','Review','website source and deployment notes','The site is ready for client review. Keep the source handoff instructions with the client context.'),
        ('Packaging system','Delivered','approved packaging print notes','The final packaging notes are already approved. Preserve the delivery record without inventing a new follow-up.'),
    ]
    rows=io.StringIO();writer=csv.writer(rows,lineterminator='\n')
    writer.writerow(['Name','Status','Client','Due date','Deliverables'])
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr('Continuity brief.md',
            '# Continuity brief\n\nAvery is an independent designer ending an agency engagement with three client handoffs still on record.\n\n'
            'Avery kept an authorized export before shared-workspace access ended. This scenario does not recover an inaccessible account or bypass permissions.\n\n'
            'The immediate job is to finish the Northstar handoff: find its brief, obtain final approval, record delivery and keep a local receipt-check task.\n\n'
            'Avery, the clients and this illustrative scenario are fictional. The files are purpose-created demo content, not customer evidence.\n\n'
            'No automation or original access policy is established by this export. Any new application rule must be explicitly declared.\n')
        for i,((client,context),(title,status,deliverables,brief)) in enumerate(zip(clients,jobs)):
            client_id=hashlib.sha256(f'handoff-client-{i}'.encode()).hexdigest()[:32]
            page_id=hashlib.sha256(f'handoff-project-{i}'.encode()).hexdigest()[:32]
            bundle.writestr(f'{client} {client_id}.md',f'# {client}\n\n{context}\n\nContact details are deliberately omitted from this fictional demo.\n')
            writer.writerow([title,status,client,f'2026-11-0{i+1}',deliverables])
            asset=f'handoff-{i+1}.txt'
            body=(f'# {title}\n\n{brief}\n\n## Handoff scope\n{deliverables}.\n\n'
                  f'[Client context](../{client}%20{client_id}.md)\n[Included handoff notes]({asset})\n\n'
                  '## Handoff checklist\n- [x] Confirm the brief\n- [x] Prepare working files\n'
                  f'- [{"x" if status=="Delivered" else " "}] Get final approval\n\n'
                  'The included TXT is a usable example handoff note; production artwork/source archives are not included in this demo.\n')
            bundle.writestr(f'Handoffs {database}/{title} {page_id}.md',body)
            bundle.writestr(f'Handoffs {database}/{asset}',f'{client} — {deliverables}\n\n{brief}\n\nPurpose-created example notes, not real customer assets.\n')
        bundle.writestr(f'Handoffs {database}.csv',rows.getvalue())
    return output.getvalue()
