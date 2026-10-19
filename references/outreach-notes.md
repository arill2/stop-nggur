# Outreach notes — what actually works

Written after sending a few thousand applications and getting very little back.
The lesson was not "send more". It was "send fewer, to people who care".

## Why volume stops working

A `careers@` inbox at a large company receives hundreds of speculative
applications a week. Yours is competing with people who have referrals. The
marginal value of application number 1,500 is roughly zero, and the cost is real:
your domain's sender reputation.

Gmail and Outlook score senders on complaint rate. One in a thousand recipients
hitting "report spam" is enough to start throttling you. At 1,500 cold emails
that is one or two annoyed recipients.

## What to do instead

1. **Target companies that actually hire for the role.** A penetration testing
   firm has a reason to read an unsolicited pentest application. A yoga studio
   with a `careers@` catch-all does not.
2. **Find the named person** where the company publishes one — a security lead
   on the team page, not a guessed `firstname.lastname@`. Then it is not cold
   outreach, it is a specific enquiry.
3. **Reference something concrete.** One line about their product, their bug
   bounty scope, or a disclosed report of theirs beats three paragraphs of
   self-description.
4. **Lead with the constraint, not the apology.** "I am in school, so I work
   remotely and part-time" is a fact a freelance-friendly team can work with.
   Burying it wastes everyone's time and reads as evasive.
5. **Offer a small first step.** A pilot audit is a decision someone can make in
   one meeting. "Hire me" is not.

## On the "still in school" disclosure

Say it in the first two lines. Reasons:

- Teams that cannot use a part-time remote person filter you out immediately,
  which saves you the follow-up.
- Teams that *can* now have a reason to keep reading — you are cheap, motivated,
  and already shipping work.
- Hiding it and revealing it later reads as a bait-and-switch.

## Signals that a company is worth contacting

- Runs a public bug bounty or VDP (they already work with external researchers)
- Has a security team page or `security.txt` with a real contact
- Hires remotely, or is small enough that remote is normal
- Publishes a hall of fame / thanks page — they acknowledge outside reports

## Signals to skip

- Catch-all mail domains where every address resolves
- Companies with no technical hiring at all
- Anywhere you would be the 500th application to a `noreply@` alias

## Measuring

Track replies, not sends. `data/sent_log.csv` gives you the denominator. If 50
sends produce zero replies, the problem is targeting or copy, not volume — and
sending 500 more will produce zero replies faster.
