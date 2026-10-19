---
name: stop-nggur
description: Autonomous job-application pipeline for an AI agent. Discovers published contact addresses for a list of target companies, verifies their mail domains, de-duplicates against a permanent suppression list, renders application emails from a template, and sends them through Composio Gmail under a hard daily cap. Use when the user asks the agent to apply for jobs, freelance work, or contract engagements at many companies; to find careers/HR/security contact addresses; to rebuild or resume an interrupted application campaign; or to check what has already been sent. Enforces no-duplicate-send and mandatory opt-out. Sending requires explicit human approval.
---

# Job Application Pipeline — agent contract

You are the operator. The user supplies intent and approval; you run the stages.

Every stage is idempotent and reads/writes only under `data/`. A run can be
interrupted at any point and resumed by re-running `doctor.py`.

## Rule zero

**Never transmit email without explicit human approval for that specific run.**
`send.py` is dry-run by default. You may run the dry run freely. You must not
add `--send` unless the user has said to send, in this conversation.

Everything else — discovery, verification, dedupe, composition — is safe to run
autonomously.

## Boot sequence

Always start here. It returns a state machine, not just a pass/fail.

```bash
python3 scripts/doctor.py --json
```

Read `ready` and `next`.

- `ready: false` → fix each entry in `blocking` using its `fix` string, then
  re-run. Do not proceed while blocked.
- `ready: true` → run the stage named in `next`.

`next` is one of `discover`, `verify`, `dedupe`, `compose`, `send`, derived from
which `data/` files are empty. Trust it over your own reading of the filesystem.

## Stages

### discover — find published addresses

```bash
python3 scripts/discover.py domains.txt --max-pages 6 --delay 2
```

Reads `domains.txt` (one domain per line). Crawls `/contact`, `/careers`,
`/about`, and `security.txt`. **Collects only addresses the company published.**

Output `data/candidates.json`: `[{domain, email, source_url}]`

A domain that yields nothing is reported with a reason (`no page fetched` vs
`pages fetched, no address published`). That is a legitimate outcome. **Do not
guess addresses to fill the gap** — that turns this into address harvesting and
is the single fastest way to get the user's domain blacklisted.

### verify — confirm the domain accepts mail

```bash
python3 scripts/verify.py
```

DNS MX lookup only. Safe, no contact with the target.

Output `data/targets.csv`: `[company,email,mx,catch_all,verified,source_url]`,
sorted best-first, dead domains removed.

`--probe` additionally opens SMTP sessions to test whether a mailbox exists.
**Do not enable `--probe` unless the user asks for it.** It is detectable, often
against provider policy, and unnecessary when you already have a published
address.

### dedupe — guarantee no repeat contact

```bash
python3 scripts/dedupe.py --limit 20 --per-domain 1
```

This is the stage that makes duplicates impossible. It subtracts:

- everything in `data/suppression.txt`
- every `sent`, `bounced`, or `unsubscribed` row in `data/sent_log.csv`
- anything beyond the per-domain cap, keeping the best inbox first
  (careers > security > hello/info > admin/sales > anything)

Output `data/queue.json`. If the queue is empty, everything is already sent or
suppressed. **That is correct behaviour, not a failure.** Report it and stop.

### compose — render the emails

```bash
python3 scripts/compose.py --template templates/en_penetration_tester.txt
```

Injects `SENDER_*` from `.env` and `{company}` / `{position}` per recipient.

Refuses to render a template with no opt-out line. Do not work around this with
`--allow-no-optout` unless the user explicitly instructs it and understands that
unsolicited mail without an opt-out is spam in most jurisdictions.

Output `data/outbox.json`: `[{company,email,subject,body}]`

Show the user the rendered preview before moving on. This is the last cheap
moment to catch a bad template.

### send — transmit

```bash
python3 scripts/send.py                                    # dry run, always safe
python3 scripts/send.py --send --limit 5 --attachment ~/cv.pdf
```

Requires `--send`. Re-checks the suppression list at send time so a stale queue
cannot cause a duplicate. Enforces `--daily-cap` (default 20) counted from the
log, not from memory.

Output: appends to `data/sent_log.csv` with status `sent` / `failed` / `timeout`.

**Report success only from the log.** Composio can return a process exit code of
0 with `successful: false` in the payload. `send.py` already handles this; do not
second-guess it by parsing stdout yourself.

### track — inspect and honour opt-outs

```bash
python3 scripts/track.py status --json
python3 scripts/track.py optout someone@example.com
```

Any inbound "STOP", "unsubscribe", or "don't contact me" → run `optout`
immediately, same session. This is not optional and not deferrable.

## Invariants

These hold across every stage. Violating one is a bug, not a judgement call.

1. **No guessed addresses.** Only `discover.py` output enters the pipeline.
2. **Suppression is absolute.** `common.load_suppression()` merges the
   suppression file with all terminal log states. Any new code must call it.
3. **No send without `--send`.**
4. **Daily cap stays at 20** unless the user explicitly raises it.
5. **Opt-out line stays in every template.**
6. **`data/` is never committed.** It holds real people's addresses.

## Failure playbook

| Symptom | Meaning | Action |
|---|---|---|
| `no candidates` | nothing published found | widen `domains.txt`; do not guess |
| `queue is empty` | all sent or suppressed | correct outcome; report and stop |
| `composio CLI not found` | not installed | run the `fix` from `doctor.py` |
| `template has no opt-out line` | template edited | restore the footer |
| `daily cap reached` | cap hit today | stop; resume tomorrow |
| all sends `ERR` | Composio auth expired | `composio login`, then retry |
| `doctor` exit 1 | blocking check failed | fix `blocking[]`, re-run |

## Reporting format

After each stage, report one line: stage, count in, count out, and any drops with
the reason. After a send run: sent, failed, first error, remaining queue.

Example:

```
discover  3 domains  -> 2 addresses (1 domain published nothing)
verify    2 addresses -> 2 usable (mx ok)
dedupe    2 -> 1 queued (1 over per-domain cap)
compose   1 rendered
send      1 sent, 0 failed, 0 remaining
```

Do not pad this. The user is tracking outcomes, not activity.
