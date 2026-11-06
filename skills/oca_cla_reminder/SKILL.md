---
name: oca_cla_reminder
description: Find your open OCA pull requests whose "CLA Signing" check fails, work out which commit authors block it (usually original authors replayed by a migration), and remind them - an @-mention PR comment for authors with a GitHub login, an email for authors known only by email. Use when the user asks which PRs miss a CLA, why the OCA CLA check fails, or to ask contributors to sign the CLA.
---

# Remind OCA contributors to sign the CLA

OCA's CLA check covers every commit author in a PR. Migration PRs replay the
module's history, so earlier contributors who never signed (or whose email is
missing from their company's CLA) make the check fail even though the PR
author signed.

## 1. List PRs with a failing CLA check

```bash
gh api -X GET search/issues -f q="is:pr is:open author:<login> org:OCA" -f per_page=100 \
  --jq '.items[] | "\(.repository_url | sub(".*/repos/";""))#\(.number)"'
```

For each PR read the head SHA and the CLA status:

```bash
sha=$(gh api repos/<repo>/pulls/<n> --jq .head.sha)
gh api repos/<repo>/commits/$sha/status \
  --jq '.statuses[] | select(.context | test("cla";"i")) | "\(.context)=\(.state)"'
```

`CLA Signing=failure` is a missing CLA. No CLA status on an OCA PR means the
check did not run; a new push re-triggers it.

## 2. Find who blocks it

The `oca-cla-bot` comment on the PR lists the emails that need to sign:

```bash
gh api repos/<repo>/issues/<n>/comments \
  --jq '.[] | select(.user.login | test("cla-bot")) | .body'
```

Map each email to a GitHub login through the PR's commits:

```bash
gh api "repos/<repo>/pulls/<n>/commits?per_page=250" \
  --jq '.[] | "\(.author.login // "-")\t\(.commit.author.email)\t\(.commit.message | split("\n")[0])"'
```

`-` means the email is not linked to any GitHub account. Note which commit each
author wrote (e.g. the 16.0 migration) for the message.

## 3. Draft the reminders - show them before sending

Keep both short. Always show the drafts and wait for approval: @-mentions
notify people and emails cannot be taken back.

**PR comment** (one comment for all authors with a login):

> Hi @login1 @login2, your earlier commits are part of this migration, and the
> CLA check fails for email1 and email2. Could you sign at
> https://clabot.odoo-community.org/ (or have them added to <Company>'s company
> CLA)? Thanks!

**Email** (one per author without a login):

> Subject: OCA CLA for <module>
>
> Hi <first name>,
>
> Your <version> commit is part of my <target> migration of <module>
> (<PR URL>), and the CLA check fails for <email>. Could you sign at
> https://clabot.odoo-community.org/ (or have it added to <Company>'s company
> CLA)?
>
> Thanks,
> <your name>

Mention the company CLA when the email domain belongs to a company whose other
contributors pass the check: adding the email there is usually all it takes.

## 4. Send

- Comment: `gh api -X POST repos/<repo>/issues/<n>/comments -f body='...'`
- Email: the user's mail connector (e.g. Gmail `send_message`), plain-text body.

Report the comment URL and that the email was sent.
