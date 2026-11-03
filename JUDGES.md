# Judge walkthrough

Live product: https://exitforge.site

The shared new-input AI trial is exhausted. This walkthrough opens saved **actual**
Meta outputs on synthetic sources, makes no new inference call and requires no
customer account connection. The receipt preserves original model output, source
bindings and the approved policy separately. Do not describe this as a new live
model request.

## Client delivery

1. Choose **Rebuild a working process**.
2. Expand **What Meta observed**, inspect **Source relationship coverage**, and
   inspect the original semantic proposal. The current saved example is from
   the real November 3 source-binding verification.
3. Choose **Move parent to Changes requested**, then check confirmation and open.
4. On Brand launch, try **Hand over** before approving Logo pack. It is blocked.
5. Request changes on Logo pack. Only its parent follows the selected policy.
6. Mark it Approved and Hand over. Inspect **Follow-ups**: exactly one contextual
   receipt task exists. Repeating handover adds no duplicate.
7. Inspect **Client handoff**. Notes and files start excluded. The preview shows
   only the selected project and linked items; sharing requires your own action.
8. Choose **Take it with you**, download independent HTML, open it in a desktop
   Chromium browser, disconnect and continue. Create a project/item, use the same
   approval guard, reload, download a backup and re-export.

## Publication workflow

Choose **Try editorial workflow**. This is a second saved actual Meta response
from November 3, with different fields/states: Publication step, Sign-off,
Amend/Accepted and Revision/Released. Confirm a revision policy, attempt premature
handover, approve the missing item and inspect the contextual task. It uses the
same engine rather than a separate hard-coded editorial application.

## Reproduce locally

From a clean repository, enter `app/` and run:

```sh
python -m exitforge.server --port 8766
```

Open http://127.0.0.1:8766. Python 3.12+; no provider key or third-party runtime
dependency is required for recorded examples or the offline core. Run tests using
the commands in `app/README.md`. Example observation images are local assets.

No original SaaS permissions, external notifications, arbitrary automations or
recipient acknowledgments are recreated. Only retain/export work you are allowed
to keep. Downloaded apps and ZIPs contain source data; keep backups and inspect
selected notes/files before sharing.
