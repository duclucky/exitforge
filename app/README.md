# ExitForge

**Your export becomes a working application you can keep using.**

Live studio: [exitforge.site](https://exitforge.site).

ExitForge helps independent workers finish authorized client work after access
changes. Exported records preserve content but may lose operational context.
ExitForge combines Notion-style Markdown/CSV exports with ordered workflow
observations, asks Meta for a bounded semantic proposal, and turns a reviewed
policy into an editable self-contained HTML application.

## Try it in three minutes

No customer account connection or API key is needed for the recorded examples.

1. Open **Rebuild a working process** for client delivery, or **Try editorial
   workflow** for publication. Both are saved actual Meta responses on fictional
   data; opening them makes no new inference request.
2. Inspect observations, complete source relationships and the untouched model
   proposal. Choose the parent-stage revision policy and explicitly confirm.
3. Try **Hand over** before approving the first item: the guard blocks it.
   Request changes, approve, then hand over. Only its linked parent changes;
   repeating handover does not create another local receipt task.
4. Download independent HTML, open it in a desktop Chromium browser and disconnect.
   Create/edit projects and items, reload, back up and re-export. Browser storage
   is local and may be cleared; keep regular backups.
5. **Client handoff** exports a separate one-project ZIP with a passive recipient
   page and selected files. Notes/files start excluded. No client message is sent.

The hosted new-input AI trial has exhausted its five shared operations. Saved
actual examples, manual review, import and exports remain available. This is a
usage limit, not a claim that a new live inference is taking place. Source and
screenshots go to Baseten only after fresh consent for a requested AI call.
Hosted import/packaging use the VPS; drafts stay in browser storage. Independent
HTML needs no provider connection.

## Run locally

Python 3.12+ is sufficient for the loopback studio. Import, saved proposals,
review, client packs and independent export need no third-party runtime package.
Enter `app/` first when using the submission repository wrapper.

```sh
python -m exitforge.server --port 8766
```

Open http://127.0.0.1:8766. The loopback development server is not a public Internet
server. The bounded public ASGI adapter uses `requirements-web.lock` and Docker.
Hosting configuration is separate from the portable application.

Optional provider setup: copy `.env.example` to a private `.env`, then use a
launcher that exports its variables. The standard server does not load `.env`.
Never commit credentials. Cloud operations require `EXITFORGE_ALLOW_CLOUD=1`;
review provider billing before enabling them.

## What Meta does

The verified route uses **Meta Muse Spark Open**, exact event identifier
`meta-models/muse-spark-open-1026`, served by Baseten. It proposes status-field
bindings and semantics for approval, revision and guarded parent handover from
source excerpts and ordered screenshots, citing observation evidence.

The source resolver, not the model, supplies every unique explicit relationship
and observed state. Ambiguous bindings stop before a paid call. Strict validation
rejects unsupported/contradictory proposals. Human policy selection and confirmation
precede execution. Model output never executes as generated application code.
The shared deterministic action engine runs online and in independent HTML.

The receipt distinguishes raw model output, source-derived bindings and approved
policy. Both process examples retain actual November 3 responses and observation
hashes. They are saved proposals, not new requests. Earlier single-database source
interpretation/view generation is also retained.

Direct Meta API and Fireworks are not used by the verified hosted route. A
historical private Modal compiler was verified; the current hosted Modal route
is unavailable. No all-four-provider completion or Muse Code use is claimed.

## Verification and limits

The current suite contains 82 Python tests and 36 JavaScript tests. Node.js 20+
is required for JavaScript tests and one Python-to-JavaScript ZIP interoperability
test; it is not a product runtime dependency. From `app/`:

```sh
python -m unittest discover -s tests -p "test_*.py"
node --test tests/foundation.test.cjs tests/handoff.test.cjs tests/process.test.cjs tests/records.test.cjs tests/workflow.test.cjs
```

Python tests use standard library fixtures, isolated HTTP servers and fake provider
transports, with no paid calls. Browser scripts separately require Playwright and
Chromium. Submission evidence identifies completed checks; command listings alone
are not verification.

Real November 3 delivery and editorial requests each resolved 4/4 explicit links;
review, revision/approval, one task and offline use were checked separately.
Earlier failures remain historical. These small synthetic cases are not a general
accuracy score. Real-user demand, adoption and time savings remain unmeasured.

Supported scope: bounded two-database parent/child workflows, three action kinds,
explicit source links and selected observations. Hidden permissions, external
notifications and arbitrary SaaS automations are not recovered. Selected free
text/files require human review before sharing. Client ZIPs are unencrypted;
local workflow states do not establish recipient acknowledgment or signature.

## Architecture

- `exitforge/importer.py`: bounded ZIP recovery and source identity.
- `exitforge/process_bindings.py`: complete explicit source graph.
- `exitforge/processes.py`: Meta semantic contract and strict validation.
- `static/process.js`, `process-records.js`: deterministic shared runtime.
- `static/handoff.js`, `handoff-view.js`: scoped client ZIP and passive page.
- `exitforge/compiler.py`: self-contained HTML with no network dependency.
- `exitforge/asgi.py`, `public_ai.py`: exact-origin public transport, consent,
  durable precharged quota, idempotency and bounded concurrency.

## License and contribution

MIT. Preserve dependency licenses/attribution. Demonstration records, observations
and attachments are purpose-created synthetic examples. Ducky is the sole human
participant. OpenAI Codex assisted with research, implementation, tests, debugging,
deployment and submission preparation; it is not a human teammate. The submission
repository includes a detailed event contribution and evidence statement.
