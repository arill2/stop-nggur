<div align="center">

# stop-nggur

**A job-application pipeline that an AI agent can actually operate.**

Finds published contact addresses · verifies the mail domain · guarantees it never emails the same company twice · refuses to send without an opt-out.

`Python 3.9+` · `no required deps except dnspython` · `~1,000 lines` · `MIT`

</div>

---

## The problem with "apply to 1,500 companies"

I built that version first. It sent over 1,500 applications.

It also:

- mailed one agency **seventeen times** and another six — including two of its employees by name — because nothing tracked who had already been contacted
- scraped `careers@` addresses into a file that would have published thousands of strangers' emails if I had committed it
- sent to yoga studios and breweries, because a regex matched `careers@` on a domain that happened to be in a list
- put an API key in plaintext on line 21 of the sender

The last 800 of those went to catch-all domains and guessed inboxes — addresses that had no reason to read them. Volume was never the variable that was failing.

This repo is the rewrite. It does less, on purpose.

---

## What it does

```
domains.txt
     │
     ▼
┌──────────────────────────────────────────────────────────────┐
│ discover.py   crawl /contact /careers /about + security.txt  │
│               collect ONLY addresses the company published   │
└───────────────────────────┬──────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ verify.py     DNS MX lookup — confirms the domain takes mail │
│               optional SMTP probe, behind a flag, capped     │
└───────────────────────────┬──────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ dedupe.py     subtract suppression list + full send history  │
│               keep the best inbox per company, drop the rest │
└───────────────────────────┬──────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ compose.py    render template with your identity             │
│               refuses to run if the opt-out line is missing  │
└───────────────────────────┬──────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────┐
│ send.py       dry run by default · --send to transmit        │
│               daily cap · throttle · suppression re-check    │
└───────────────────────────┬──────────────────────────────────┘
                            ▼
                      track.py    status · honour opt-outs
```

Every stage is idempotent. Interrupt it anywhere, re-run `doctor.py`, and it picks up from the right place.

---

## Quick start

```bash
git clone https://github.com/arill2/stop-nggur
cd stop-nggur

python3 -m venv .venv && source .venv/bin/activate
pip install dnspython

cp .env.example .env
$EDITOR .env                     # your name, email, phone
```

Check the machine before you run it:

```bash
python3 scripts/doctor.py
```

```
[PASS] python_version   3.14
[PASS] dnspython        installed
[PASS] composio_cli     /usr/local/bin/composio
[PASS] identity_env     Your Name <you@example.com>
[PASS] gitignore        ok
[PASS] credential_leak  clean
[PASS] pipeline_state   candidates=0, targets=0, queue=0, outbox=0, suppressed=0, sent_today=0

READY
```

`BLOCKED` prints a `fix:` line under each failure. Fix those, re-run, continue.

Then run a campaign:

```bash
printf '%s\n' portswigger.net intigriti.com > domains.txt

python3 scripts/discover.py domains.txt     # published addresses only
python3 scripts/verify.py                   # MX check
python3 scripts/dedupe.py --limit 20        # no repeats, one per company
python3 scripts/compose.py                  # render, opt-out enforced
python3 scripts/send.py                     # dry run — read it
python3 scripts/send.py --send --limit 5 --attachment ~/cv.pdf
```

Sending needs Composio:

```bash
curl -fsSL https://composio.dev/install | bash
composio login
composio add gmail
```

Discovery, verification, dedupe and composition all work without it.

---

## Guardrails, and why each one exists

These are not features. They are the scars from the first version.

| Guard | Enforced in | The failure it prevents |
|---|---|---|
| Dry run is the default | `send.py` | sending a template with a typo to 50 people |
| `--send` required to transmit | `send.py` | an agent deciding to send on its own |
| Daily cap, default 20 | `send.py` | Gmail suspending the account for cold-mail volume |
| Permanent suppression list | `common.py` | emailing someone who already said stop |
| Opt-out line required | `compose.py` | unsolicited mail that is legally spam |
| One address per company | `dedupe.py` | five applications to one HR inbox |
| Published addresses only | `discover.py` | address harvesting, which is what gets domains blocklisted |
| SMTP probe opt-in + capped | `verify.py` | hammering mail servers that log every probe |
| Secret scan at preflight | `doctor.py` | committing an API key, again |
| `data/` gitignored | `.gitignore` | publishing thousands of strangers' email addresses |

The suppression list is merged from two sources — a file, and every `sent` / `bounced` / `unsubscribed` row in the log. A stale queue cannot cause a duplicate, because the check happens again at send time.

---

## Built for an agent, not a human

`SKILL.md` is the contract. `README.md` is for whoever installs it.

The difference matters. A human reads prose and infers. An agent needs:

- **a machine-readable preflight** — `doctor.py --json` returns `{ready, blocking[], next}`
- **a state machine, not a checklist** — `next` is derived from which `data/` files are empty, so the agent never has to guess which stage to run
- **structured output** — `track.py status --json`, JSON at every stage boundary
- **invariants it cannot argue with** — six numbered rules in `SKILL.md`, each with the failure mode that produced it
- **a failure playbook** — symptom → meaning → action, for every error the pipeline emits

```bash
python3 scripts/doctor.py --json
```

```json
{
 "ready": true,
 "blocking": [],
 "next": "dedupe",
 "checks": [
  {"check": "dnspython", "ok": true, "detail": "installed", "fix": ""},
  {"check": "credential_leak", "ok": true, "detail": "clean", "fix": ""},
  {"check": "pipeline_state", "ok": true,
   "detail": {"candidates": 2, "targets": 2, "queue": 0, "outbox": 0, "suppressed": 0, "sent_today": 0},
   "fix": ""}
 ]
}
```

Point your agent at the directory and tell it to read `SKILL.md`. It will run preflight, follow `next` through the stages, and stop before sending to ask for approval.

---

## The one thing it will not do

**It will not guess an email address.**

No `firstname.lastname@`, no dictionary of common local-parts against a mail server, no catch-all exploitation. If a company does not publish a contact address, the pipeline reports that and moves on.

That constraint is why it finds fewer addresses than a scraper would. It is also the reason the result is something you can put your name on.

---

## Compliance

Read [`references/compliance.md`](references/compliance.md) before the first send.

Cold email rules diverge sharply and the differences are not cosmetic:

| Region | Rule | Effect |
|---|---|---|
| Germany | UWG §7 | cold email for advertising is **prohibited** without prior consent |
| EU/EEA | GDPR + ePrivacy | needs a lawful basis; several states require opt-in |
| US | CAN-SPAM | allowed, but needs a physical address and a working opt-out |
| UK | PECR | B2B corporate subscribers exempt; sole traders are not |
| Indonesia | UU PDP 27/2022 | personal-data processing needs a lawful basis |

If you are unsure which applies, the strictest one binds you. The tool will not make that decision for you.

---

## Honest limitations

- **It does not get you hired.** It removes the mechanical failure modes — duplicates, dead domains, missing opt-outs. Targeting and copy are still on you.
- **`discover.py` misses a lot.** Many companies publish no address at all, or render it with JavaScript. It reports why a domain yielded nothing rather than inventing a fallback.
- **MX is not delivery.** A domain with valid MX can still bounce you. The log records failures; it does not predict them.
- **Composio is a dependency for sending.** If the CLI changes its output shape, `send.py` may misreport. Check `data/sent_log.csv`, not stdout.
- **The daily cap is conservative.** That is deliberate. Raise it only if you understand what you are trading.

---

## Layout

```
SKILL.md              agent contract — the entry point for an AI
README.md             this file
scripts/
  doctor.py           preflight + state machine
  discover.py         published addresses only
  verify.py           MX, optional SMTP probe
  dedupe.py           suppression + per-domain cap
  compose.py          render, opt-out enforced
  send.py             dry run default, daily cap
  track.py            status, opt-out handling
templates/            en_ / id_ application templates
references/
  compliance.md       jurisdiction rules
  outreach-notes.md   why small batches beat large ones
data/                 runtime state — gitignored, never commit
```

---

<div align="center">

MIT · built after 1,500 applications taught me that volume was the wrong variable

</div>
