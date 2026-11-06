---
name: oca_pr_checks
description: Check the CI checks of an OCA pull request (GitHub Actions "test with Odoo" / "test with OCB", pre-commit, runboat, CLA), read the failing job logs from a PR number or an actions/runs/<run>/job/<job> URL, reproduce the failure locally (odev, doodba or plain odoo-bin), fix it and amend the fix into the PR's single [MIG] commit. Use when the user pastes an OCA PR or GitHub Actions job link, or asks why OCA CI / PR checks fail or to fix them.
---

# Check & fix OCA PR checks

## Inputs

Derive from the request:

| Input                                                                       | Gives                         |
| --------------------------------------------------------------------------- | ----------------------------- |
| `https://github.com/OCA/<repo>/pull/<pr>`                                   | `repo`, `pr`                  |
| `https://github.com/OCA/<repo>/actions/runs/<run>/job/<job>?pr=<pr>`        | `repo`, `run`, `job`, `pr`    |

The local checkout is the user's clone of `<repo>` (in a doodba project:
`<project>/odoo/custom/src/<repo>`), on the PR's head branch
(`gh pr view <pr> -R OCA/<repo> --json headRefName,headRepositoryOwner`).

## 1. Overview of the checks

```bash
gh pr checks <pr> -R OCA/<repo>
```

**Waiting for CI to finish**: `gh pr checks` exits non-zero as soon as *any* check failed (e.g. CLA
Signing), so never use its exit code as the loop condition — a loop like
`until s=$(gh pr checks …) && ! grep -q pending …` then never ends. Check only for `pending`:
```bash
until ! gh pr checks <pr> -R OCA/<repo> 2>/dev/null | grep -q pending; do sleep 30; done
gh pr checks <pr> -R OCA/<repo>
```
(run it in the background; give it a timeout).

## 2. Read the failing logs

`gh run view --job <job> --log-failed` prints only the failed steps. Strip the job/step/timestamp
prefix and grep the essentials:

```bash
gh run view -R OCA/<repo> --job <job> --log-failed \
  | sed -E 's/^[^\t]*\t[^\t]*\t[0-9TZ:.-]+ //' \
  | grep -E 'ERROR|FAIL|Traceback|Error:|tests when loading' | head -60
# full traceback of one test:
gh run view -R OCA/<repo> --job <job> --log-failed | sed -E 's/^[^\t]*\t[^\t]*\t[0-9TZ:.-]+ //' \
  | grep -n -m1 -A50 'ERROR: <TestClass>.<test_name>'
```

Without a job id: `gh run list -R OCA/<repo> --branch <head_branch>` →
`gh run view <run> -R OCA/<repo>` lists the jobs with ids.

## 3. Triage per check

- **test with Odoo / test with OCB**: CI installs **all** installable addons of the repo in one DB
  and runs all their tests. A failure in *another* module's tests is usually caused by the PR's
  module (new ACLs, required fields, overridden methods, stored related fields). Look at which
  module the traceback points to (our module path vs. the failing test's module).
  OCB and Odoo jobs usually fail the same way — fix once.
- **pre-commit**: run `pre-commit run --files $(git ls-files <module>)` locally; commit hook fixes.
- **Detect unreleased dependencies**: a dependency in `test-requirements.txt` / manifest points to
  an unmerged PR — that's expected while a dependency PR is open; tell the user. Nothing to fix:
  it turns green once the dependency PRs are merged and `test-requirements.txt` is removed.
- **runboat/build**: open the build link; usually follows the test failure.
- **codecov/patch, codecov/project**: don't add tests or change code just to raise coverage, not
  even as part of "fix the tests". Only mention it in the summary with the numbers from the check
  (e.g. `codecov/patch: 91.86% of diff hit (target 96.77%)`), via
  `gh api repos/OCA/<repo>/commits/<sha>/check-runs --jq '.check_runs[]|select(.name|test("codecov"))|.output.title'`.
- **CLA Signing**: the commit author email has no signed OCA CLA
  (`gh api repos/OCA/<repo>/commits/<sha>/statuses --jq '.[]|select(.context|test("CLA"))'`).
  Can't be fixed by code — tell the user to sign at https://odoo-community.org/page/cla (individual,
  or get added to the company CLA) for the email in `git log -1 --format='%ae'`.

## 4. Reproduce locally

Install the PR's module **together with the failing module(s)** on a fresh or throwaway database
and run both test sets. Use the runner the setup has:

```bash
# odev (temporary copy of the migration DB; create it with
# `odev create -f -V 20.0 <module>_mig_20 <repo_path>` if missing)
cd <repo_path>
odev test <module>_mig_20 -i <module>,<failing_module> -t /<module>,/<failing_module> $PWD > <log> 2>&1

# doodba: see the doodba skill ("Tests"), e.g.
invoke test --modules=<module>,<failing_module> > <log> 2>&1

# plain odoo-bin
odoo-bin -d <scratch_db> --addons-path=<odoo>/addons,<repo_path>,<deps...> \
  -i <module>,<failing_module> --test-enable --test-tags /<module>,/<failing_module> \
  --stop-after-init > <log> 2>&1

grep -E 'tests when loading|ERROR: |FAIL: ' <log>
```

Closest to CI, needs only Docker: run the CI image itself (`matrix.container` in the repo's
`.github/workflows/test.yml`) — see "No Odoo setup at all" in the `oca_migration_git` skill,
phase 3. It installs all addons of the repo like CI does.

Dependencies that aren't on 20.0 yet must come in the way the setup manages code (doodba:
`repos.yaml` merges — see the `doodba` skill), not by copying modules into temp folders. odev
pitfalls (pruning prompt, WSL npm) are listed in the `oca_migration_git` skill.

Confirm the same errors appear before fixing.

## 5. Fix

- Fix in the PR's module, not in the other module (unless that one is really broken on the target
  branch — then tell the user).
- Add a regression test in the PR's module reproducing the CI scenario (e.g. the same user groups).
- Re-run step 4 until `0 failed, 0 error(s)`.
- All own changes stay in the single `[MIG]` commit:
  ```bash
  git add -A && git commit --amend --no-edit       # runs pre-commit hooks
  git push --force-with-lease <user_org> <head_branch>
  ```
- If the fix is a non-obvious change, add one bullet to the PR body (short, rules in the
  `oca_migration_git` skill, Phase 5) and update fork + OCA PR with
  `gh api -X PATCH repos/<owner>/<repo>/pulls/<n> -F body=@<body.md>` (`gh pr edit` may fail with a
  Projects-classic GraphQL error).
- Reviewer asks to "squash the administrative commits" (bot `.pot`/`[BOT] post-merge`/Weblate
  commits replayed from the previous version), see the OCA wiki
  https://github.com/OCA/maintainer-tools/wiki/Merge-commits-in-pull-requests#mergesquash-the-commits-generated-by-bots-or-weblate:
  turn each into a `fixup` of the commit before it with the `GIT_SEQUENCE_EDITOR` rebase from the
  `oca_migration_git` skill ("Squash administrative commits"). Rebase from the module's first commit
  (not `origin/<target>`) so older commits keep their SHAs, check `git diff <old_head> HEAD` is
  empty, force-push, and comment on the PR that the commits are squashed.
- `gh pr checks <pr> -R OCA/<repo>` to confirm the new run started; report results honestly (pending /
  passed / failed).

## Known Odoo 20 CI failures

- `AccessError: Failed to write field <model>.<m2m_field>` / "You are not allowed to access
  '<Comodel>'" in other modules' tests: Odoo 20 checks **read access on the comodel** whenever a
  many2many is written (also when empty, e.g. a `Form` save). Grant read on the comodel to the
  lowest group that edits the record (e.g. `account.group_account_invoice` for invoice fields, not
  only `account.group_account_user`). Tests using `BaseCommon` with
  `_test_user_groups = ("account.group_account_invoice",)` expose this.
