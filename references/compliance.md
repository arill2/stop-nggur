# Compliance — read before you send anything

This pipeline sends unsolicited job applications. That is legal in some places
and illegal in others. You are responsible for where you point it.

## The short version

Cold email to a generic company inbox (`careers@`, `jobs@`, `hr@`) asking about
work is usually tolerated. Cold email to a **named individual** who never asked
to hear from you is where you get in trouble — and it is also the fastest way to
get your domain blacklisted.

**Do not** send to addresses you guessed. Only to addresses the company
published for the purpose of being contacted.

## Jurisdiction notes

| Region | Rule | Practical effect |
|---|---|---|
| EU / EEA | GDPR Art. 6 (lawful basis) + ePrivacy Directive | B2B cold email needs a legitimate-interest assessment; some states require opt-in |
| Germany | UWG §7 | Cold email for advertising is **prohibited** without prior consent — this includes job enquiries |
| UK | PECR + UK GDPR | B2B corporate subscribers are exempt from consent; sole traders are not |
| US | CAN-SPAM | Allowed, but requires accurate headers, a physical address, and a working opt-out honoured within 10 business days |
| Canada | CASL | Requires consent, with a narrow B2B exemption if the message is relevant to the recipient's role |
| Indonesia | UU PDP (Law 27/2022) | Personal data processing needs a lawful basis; electronic marketing needs consent |
| Australia | Spam Act 2003 | Consent required; B2B inferred consent is limited |

If you are not sure, treat the strictest applicable rule as the one that binds you.

## Rules this pipeline enforces

1. **Opt-out is mandatory.** `compose.py` refuses to render a template without
   an opt-out line.
2. **Suppression is permanent.** Once an address is in `data/suppression.txt` it
   is never contacted again, including by future runs.
3. **Daily cap.** Default 20. Change it deliberately, not by accident.
4. **One address per company.** `dedupe.py --per-domain 1` by default.
5. **No guessing.** `discover.py` only collects addresses the company published.

## SMTP RCPT probing

`verify.py --probe` opens an SMTP session to the target's mail server and asks
whether a mailbox exists. This is:

- **Detectable.** Every probe is logged by the receiving MTA.
- **Often against policy.** Most major providers' acceptable-use terms prohibit
  address harvesting and directory collection.
- **A reputational risk.** Bulk probing from a residential IP looks like
  reconnaissance to abuse teams.

It is behind a flag and capped for a reason. If you do not have a legitimate
reason to know whether a mailbox exists, do not turn it on.

## Gmail / Composio limits

- Free Gmail: ~500 recipients/day, but a much lower practical threshold before
  Google's spam filters start throttling you.
- New accounts sending cold mail get suspended quickly. Warm the account first.
- Composio's Gmail tool sends as your connected account. Everything you send is
  attributable to you.

## If someone replies STOP

    python3 scripts/track.py optout someone@example.com

Do it the same day. An unhonoured opt-out turns a grey-area email into a
complaint, and complaints are what get domains blocked.
