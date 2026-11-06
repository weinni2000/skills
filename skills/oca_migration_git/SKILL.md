---
name: oca_migration_git
description:
    "OCA-style migration of an Odoo module to a new version (default 19.0 -> 20.0), following the OCA
    wiki 'Migration to version 20.0'. Prepare mode: create the `<target>-mig-<module>` branch, replay
    the module history with `git format-patch | git am -3 --keep`, commit pre-commit auto fixes, stop.
    Full mode: additionally bump the version to `20.0.1.0.0`, remove `migrations/`,
    adapt the code and commit `[MIG] <module>: Migration to 20.0`, push both branches to the user's
    fork and open a review PR there (base branch -> migration branch). Use when the user asks to
    prepare/start/set up a migration, or to upgrade/migrate/port a module 'OCA style' / 'with the OCA
    git flow'."
metadata:
    version: "3.0"
    source: "https://github.com/OCA/maintainer-tools/wiki/Migration-to-version-20.0"
---

# OCA Module Migration

## Mode

| Request                                                              | Phases     |
| -------------------------------------------------------------------- | ---------- |
| "prepare / start / set up the migration (branch) of X"               | 0, 1       |
| "upgrade / migrate / port X OCA style", "migrate X to 20.0"          | 0 → 5      |

Phase 5 = push to the user's fork + review PR **inside the fork**. A PR against OCA itself only
when the user explicitly asks.

Don't add anyone to `readme/CONTRIBUTORS.md` and don't announce the migration in the OCA
"Migration to version XX.0" issue unless the user asks for it.

## Optional companions

The skill works with plain `git`, `gh`, `pre-commit` and `odoo-bin`. Use these when available:

| Tool / skill                       | Used for                                                       |
| ---------------------------------- | -------------------------------------------------------------- |
| [odev](https://github.com/odoo-odev/odev) (`command -v odev`) | fresh test databases, `odev upgrade-code` |
| `doodba` skill                     | repo is inside a doodba project (`repos.yaml`, gitaggregate)   |
| `odoo_upgrade_skill` (odoo-ps)     | step-by-step code adaptation workflow in phase 3               |

## Inputs

Derive from the cwd / request; ask only for what can't be derived:

| Var        | Meaning                                | Default / example                 |
| ---------- | -------------------------------------- | --------------------------------- |
| `repo`     | OCA repository                         | from `git remote -v`              |
| `module`   | technical module name                  | `account_invoice_foo`             |
| `source`   | version the module currently exists in | `target - 1` (`19.0`)             |
| `target`   | version to migrate to                  | `20.0`                            |
| `user_org` | GitHub fork owner / remote name        | `gh api user --jq .login`         |
| `oca`      | name of the OCA remote                 | `origin` (doodba: the repo name)  |

If the module is not on `<oca>/<target-1>`, check older branches
(`git ls-tree -d <oca>/<ver> -- <module>`) and use the newest one that has it.

The commands below use `origin`, `19.0` / `20.0`; substitute the real values. Always write real
values into commands you run or hand to the user — never leave `$module` etc. unset (the commit
would become `[MIG] : Migration to 20.0`).

## Phase 0 — Pre-flight

1. Working tree clean (`git status --porcelain`). Never stash/discard the user's changes without asking.
2. `git fetch origin`. Clones made by git-aggregator (doodba) are usually **single-branch**
   (`remote.origin.fetch` only maps the target) and the source branch is missing — fetch it
   explicitly:
   `git fetch origin "+refs/heads/19.0:refs/remotes/origin/19.0" "+refs/heads/20.0:refs/remotes/origin/20.0"`.
   A new OCA target branch may be a lone "Initial commit" without shared history with the source
   branch — that's fine, `origin/20.0..origin/19.0 -- <module>` then replays the whole module history.
3. Module exists on source, not on target — otherwise stop (already migrated):
   ```bash
   git ls-tree -d origin/19.0 -- <module>   # must print the dir
   git ls-tree -d origin/20.0 -- <module>   # must print nothing
   ```
4. Nobody else on it: `gh pr list -R OCA/<repo> --search "[20.0][MIG] <module>" --state open`.
   If a PR exists, tell the user and ask whether to continue.
5. `pre-commit --version` works.
6. Full mode: re-read the live wiki
   (`curl -sL https://raw.githubusercontent.com/wiki/OCA/maintainer-tools/Migration-to-version-20.0.md`)
   — the "Tasks to do in the migration" list grows during the release cycle; apply new bullets in phase 3.

## Phase 1 — Git preparation

Work **in the existing clone** the user pointed at: check out the migration branch there. Don't use
`git worktree` or create extra folders/clones — clone only if there is no local clone of the repo
at all. Note the branch the user was on (e.g. `20.0`) and mention it in the report so they can
switch back.

Repo inside a doodba project (`odoo/custom/src/<repo>` next to a `repos.yaml`)? Get it and wire the
migration branch in as described in the `doodba` skill ("Migration branches and dependency PRs").

```bash
# only if no local clone of OCA/<repo> exists
git clone https://github.com/OCA/<repo> -b 20.0 && cd <repo>

git checkout -b 20.0-mig-<module> origin/20.0
git format-patch --keep-subject --stdout origin/20.0..origin/19.0 -- <module> | git am -3 --keep
# squash administrative commits — always, see "Squash administrative commits" below
pre-commit run -a   # ignore pylint errors here; re-run until only non-auto-fixable issues remain
git add -A
git commit -m "[IMP] <module>: pre-commit auto fixes" --no-verify
```

- **Long histories** (e.g. `connector`: ~750 commits since 2013) make `git am`/`rebase` slow mostly
  because git auto-gc runs after nearly every commit ("Auto packing the repository…"). Run them
  with `git -c gc.auto=0 am …` / `git -c gc.auto=0 rebase …`, and run long ones in the background.
- pylint_odoo still reports `manifest-version-format` (old version) here — expected, the bump goes
  into the `[MIG]` commit.
- "Nothing to commit" after pre-commit is fine — skip that commit.
- `--no-verify` is intentional for this commit only (all formatting in one commit, per wiki).
- If pre-commit changes files outside `<module>/`, revert them (`git checkout -- <path>`) unless
  they're required repo-level fixes — then mention it.

**`git am` failures** ("patch does not apply", often a patch deleting a file):
```bash
git am --abort
git format-patch --keep-subject --stdout origin/20.0..origin/19.0 -- <module> | git am -3 --keep --ignore-whitespace
# inspect: git am --show-current-patch=diff ; git status
# resolve only inside <module>/ (e.g. git rm <file>), then:
git add --all && git am --continue
```
- Empty patch (already applied / touches other paths only) → `git am --skip`.
- Never blindly take one side for a whole file; show non-trivial conflicts to the user first.

**Module renamed** in the migration — rename the whole history, otherwise the next migration only
brings the latest commit:
```bash
git filter-repo --path-rename <module>/:<new_module>/ --refs HEAD --force
# without filter-repo:
# FILTER_BRANCH_SQUELCH_WARNING=1 git filter-branch -f --tree-filter \
#   'if [ -d <module> ]; then mv <module> <new_module>; fi' origin/20.0..HEAD
# git update-ref -d refs/original/refs/heads/<branch>
```

**Squash administrative commits** — always, right after `git am` and before the pre-commit commit
(wiki:
https://github.com/OCA/maintainer-tools/wiki/Merge-commits-in-pull-requests#mergesquash-the-commits-generated-by-bots-or-weblate).
Each bot/Weblate commit becomes a `fixup` of the commit before it, non-interactively:
```bash
GIT_SEQUENCE_EDITOR="perl -pi -e 's/^pick(?= [0-9a-f]+ (\[BOT\] post-merge|\[UPD\] Update .*\.pot|Translated using Weblate|Added translation using Weblate|Update translation files|\[ADD\] icon\.png|Launchpad automatic translations update|OCA Transbot updated translations|\[IMP\] update dotfiles|<module> [0-9]+\.0\.[0-9.]+\$))/fixup/'" \
  git -c gc.auto=0 rebase -i origin/20.0
git log --format='%h %an | %s' origin/20.0..HEAD   # only real commits left
git diff <head_before_rebase> HEAD --stat          # must be empty: same tree
```
- `perl -pi` instead of `sed -i` so it works with GNU and BSD/macOS alike.
- Replace `<module>` in the pattern (OCA-git-bot version-bump commits like `connector 15.0.1.0.4`).
- Check the remaining log for other bot subjects (oca-ci, OCA-git-bot) and add them to the pattern.
- If the very first commit were a bot commit, `fixup` has nothing to squash into — leave it as `pick`.

**Base branch for the review PR** — right after the pre-commit commit (or after `git am` if there
was nothing to commit), mark the state before the migration:
```bash
git branch 20.0-mig-<module>-base HEAD
```

**Prepare mode stops here.** Report the branch and:
```bash
git log --oneline origin/20.0..HEAD | head -20
git log --oneline origin/20.0..HEAD | wc -l
```

## Phase 2 — OCA administrative tasks

- `__manifest__.py` version → **`20.0.1.0.0`** (OCA convention; wins over any local "new modules
  end in `.1`" rule). Keep `author`, `maintainers`, `license`, `website`.
- Delete the `migrations/` folder if present.
- `readme/CREDITS.md` / `CREDITS.rst`: leave unchanged — don't remove credits, not even old
  "migration … financially supported by …" lines (deliberate deviation from the wiki bullet
  "Remove references in CREDITS.rst of past financed migrations").
- `readme/CONTRIBUTORS.md`: leave as it is unless the user asks.
- **Do NOT** change copyright years (`# Copyright 2024 ACME` = "from 2024") or original authors.
- Don't hand-edit `README.rst` / `static/description/index.html` — oca-gen-addon-readme regenerates them.

## Phase 3 — Code adaptation

The wiki lists framework changes only. For data-model changes of core modules see
`openupgrade_scripts/scripts/<core_module>/20.0.*/upgrade_analysis.txt` in OCA/OpenUpgrade (branch
`20.0`). When jumping several versions, also apply the tasks of every intermediate
"Migration to version XX.0" wiki page.

1. Apply every bullet of the live wiki "Tasks to do in the migration" list — **except** "Add tests
   to increase code coverage": don't add tests just for coverage (also not for failing codecov
   checks). Existing tests still have to be adapted and pass; mention missing/low coverage in the
   summary instead.
2. Automatic rewrites (views, `<tree>` → `<list>`, Font Awesome → Material Symbols, ...):
   - with odev: `odev upgrade-code -f --from 19.0 --glob '<module>/**/*' <db> <repo_path>`
   - without: `odoo-bin upgrade_code --from 19.0 --addons-path <repo_path> --glob '<module>/**/*' --dry-run`
     (target Odoo checkout; drop `--dry-run` after checking the file list).
   Run it **on the migration branch** so the change lands in the `[MIG]` commit.
   If the `odoo_upgrade_skill` is installed, follow its workflow for the rest (fail-fast static
   checks, install test, reimplement removed features instead of dropping them). Its
   commit/version rules are **replaced** here: no `[UPG]` commits, no separate bump commit —
   everything goes into the single `[MIG]` commit.
3. On breakage, find the upstream change in the Odoo 20.0 source (`git log -S "<symbol>" -- <path>`)
   and adapt to the new API.
4. Follow the repo's `AGENTS.md` / `odoo-guidelines` for code you write, but don't refactor or
   reformat untouched code — keep the diff reviewable.
5. Verify, and report honestly what ran:
   - `pre-commit run --files $(git ls-files <module>)` passes (pylint_odoo included now).
   - Install + tests on a **new** database (never `-u` the user's dev DB). Pick the runner the
     user's setup has:
     ```bash
     # odev
     odev create -f -V 20.0 <module>_mig_20 <repo_path>
     odev test <module>_mig_20 -i <module> -t /<module>

     # doodba: see the doodba skill ("Tests")

     # plain odoo-bin (20.0 checkout + venv)
     odoo-bin -d <module>_mig_20 --addons-path=<odoo>/addons,<repo_path>,<deps...> \
       -i <module> --test-enable --test-tags /<module> --stop-after-init
     ```
     Keep the created DB for the user, mention its name.
   - **No Odoo setup at all, or to mirror OCA CI exactly**: only Docker is needed. Run the
     image of the repo's `.github/workflows/test.yml` (`matrix.container`). It installs **all**
     addons of the repo plus `test-requirements.txt`, like CI does, so it's slower but catches
     cross-module failures:
     ```bash
     docker network create oca-ci
     docker run -d --name oca-ci-db --network oca-ci -e POSTGRES_USER=odoo \
       -e POSTGRES_PASSWORD=odoo -e POSTGRES_DB=odoo pgvector/pgvector:pg16
     docker run --rm --network oca-ci -v "$PWD":/repo -w /repo \
       -e PGHOST=oca-ci-db -e PGUSER=odoo -e PGPASSWORD=odoo -e PGDATABASE=odoo \
       ghcr.io/oca/oca-ci/py3.12-odoo20.0:latest \
       bash -c "oca_install_addons && oca_init_test_database && oca_run_tests"
     docker rm -f oca-ci-db && docker network rm oca-ci
     ```
   - **Dependencies not yet on 20.0** (unmerged `[20.0][MIG]` PRs, e.g. `component` in the same
     repo): add them to the repo-root `test-requirements.txt` so OCA CI installs them, e.g.
     `odoo-addon-component @ git+https://github.com/OCA/connector@refs/pull/540/head#subdirectory=component`,
     and mention the PRs in the PR body (as `OCA/<repo>#<n>`, the fork PR would link its own numbers).
     Locally, bring them in the way the setup manages code (doodba: `repos.yaml` merges, see the
     `doodba` skill) — not by copying modules into temp folders.
   - Checklist before the fork PR: `test-requirements.txt` lists every unmerged dependency PR
     (otherwise OCA CI can't install the module), `fa-` icons converted, CREDITS untouched.
   - New ruff rules on 20.0 (RUF012 on `_inherit` lists etc., PERF102): follow how sibling
     `[20.0][MIG]` PRs in the same repo solved them (e.g. `# noqa: RUF012` on declarative attributes).

### If you use odev

- `odev create` takes extra addons paths as positional argument; `odev test` runs on a temporary
  copy and drops it.
- Missing external Python deps of a dependency (`External dependency 'openupgradelib' not
  installed`): `odev venv <db> -c "pip install <pkg>"` (or the version venv under
  `~/odev/virtualenvs/20.0`) and tell the user.
- **Pruning prompt**: when `[pruning] date` in `~/.config/odev/odev.cfg` is ≥ 14 days old, any odev
  command first asks to delete "unused" databases; without a TTY it aborts with `EOFError`. Never
  choose delete. Set the date to now (`sed -i "s/^date = .*/date = $(date '+%Y-%m-%d %H:%M:%S')/"`
  on that section) — deletes nothing, postpones the question — and tell the user.
- **WSL**: if only the Windows npm (`/mnt/c/Program Files/nodejs`) is on PATH, `odev create` fails
  with "WSL 1 is not supported ... npm list". Prepend a Linux node (e.g. an nvm bin dir) to PATH.

### Odoo 20 changes seen in migrations

- `ir.model.access` is gone: replace `security/ir.model.access.csv` by `security/ir.access.csv`
  (`id,name,model_id,group_id/id,operation,domain`, `model_id` = model name, `operation` e.g. `crud`,
  `r`) and update the manifest; `git rm` the old file.
- Writing a many2many checks **read access on the comodel** (even when empty, e.g. a `Form` save).
  When the module adds an m2m to an existing model, grant read on the comodel to the lowest group
  that edits that model (e.g. `account.group_account_invoice` for `account.move`), otherwise other
  modules' tests in the repo fail in OCA CI. Test by also installing a sibling module whose tests
  use a restricted user (CI installs all repo addons together). Failing CI → `oca_pr_checks` skill.
- `website.get_current_website()` is gone: use `request.env.website` or, outside website routes,
  `request.env.context.get("host_id")`:
  `website_id = request.env.website.id or request.env.context.get("host_id")`.
- The `website` model moved to `base`: the default website is `base.default_website`
  (not `website.default_website`).
- **Name collisions with new core modules**: Odoo 20 added core `mail_tracking` and
  `mail_tracking_mass_mailing` (check `ls odoo/addons/<module>`). The OCA module must be renamed —
  follow the dependency's new name (OCA/mail#310: `mail_tracking` → `mail_recipient_tracking`, so
  `mail_tracking_mass_mailing` → `mail_recipient_tracking_mass_mailing`), rename the whole history
  (see "Module renamed" above), and update XML refs (`ref="mail_tracking.…"` →
  `ref="mail_recipient_tracking.…"`), depends, readme and comments. The migration branch keeps the
  old name (`20.0-mig-<old>`), the PR title uses the new name.
- Tests: `DISABLED_MAIL_CONTEXT` (base.tests.common) is gone; use `DISABLED_MAIL_CREATE_CONTEXT`
  plus `tracking_disable=True, mail_notrack=True` to keep the old behaviour.
- Font Awesome icons (`icon="fa-…"`, `class="fa …"`) → Material Symbols: always
  `grep -rn 'fa-' <module>`; the upgrade-code scripts from step 2 convert them (e.g. `fa-link` →
  `link`).
- x2many command tuples are replaced by `odoo.Command` (OCA review request, server-ux#1382):
  `(0,0,vals)`→`Command.create(vals)`, `(4,id)`→`Command.link(id)`, `(3,id)`→`Command.unlink(id)`,
  `(5,0,0)`→`Command.clear()` (no args), `(6,0,ids)`→`Command.set(ids)`; also `[[4, id]]` lists.
  `grep -rnE "\(\s*[0-6]\s*,|\[\[[0-6]," <module> --include=*.py` and add `Command` to the import.
- `ir.config_parameter.get_param` is gone: `get_str` / `get_int` / `get_bool` / `get_float`.

## Phase 4 — Migration commit

```bash
git add --all
git commit -m "[MIG] <module>: Migration to 20.0" -m "Assisted-by: <agent> (<model id>)"
```

All own changes live in exactly **one** `[MIG]` commit on top of the replayed history. Follow-up
work on the PR (review fixes, demo data, tests, CI fixes) is amended into that `[MIG]` commit
(`git commit --amend --no-edit` or `git reset --soft <mig>~1`-style squash) and force-pushed with
`--force-with-lease` — never add separate `[IMP]`/`[FIX]` commits.

OCA asks for an `Assisted-by:` trailer on AI-assisted commits — never omit it. Use the running
agent and model id, e.g. `Assisted-by: Claude Code (claude-opus-5-5)` or
`Assisted-by: Codex (<model>)`. The PR body ends with the same trailer
(see Phase 5).

If a pre-commit hook fails, nothing was committed: re-stage hook-modified files, fix the rest, commit
again. Show `git log --oneline origin/20.0..HEAD` and `git show --stat HEAD`.

## Phase 5 — Push to the fork + review PR in the fork (full mode)

```bash
git remote add <user_org> git@github.com:<user_org>/<repo>.git   # if missing
gh repo view <user_org>/<repo>                                    # fork must exist
git push <user_org> 20.0-mig-<module>-base 20.0-mig-<module>
gh pr create -R <user_org>/<repo> --base 20.0-mig-<module>-base --head 20.0-mig-<module> \
    --title "[20.0][MIG] <module>: Migration to 20.0" --body-file <body.md>
```

The review PR shows only the `[MIG]` commit. Report the PR URL.

**PR body** (fork PR and OCA PR share it, plus the fork-PR link in the OCA one) — short:
- Only the non-obvious code changes as bullets. Skip what every migration does (version bump,
  README regen, removed `migrations/`, squashed bot commits, pre-commit fixes). A small migration
  gets a small body — two bullets are fine.
- **No "Verification" section** (no pre-commit/test results).
- **OCA PR only**: link the fork review PR, which shows only the diff after the pre-commit auto
  fixes: `Migration changes only (diff after the pre-commit auto fixes): <fork PR URL>`. Not in the
  fork PR itself (it would link to itself).
- If odev was used: `Migrated with odev.`
- End with `Assisted-by: <agent> (<model id>)` — not a `🤖 Generated with ...` line.
- Don't claim things on the user's behalf (e.g. "reviewed by me").

Example (OCA PR):
```markdown
- Convert `security/ir.model.access.csv` to `security/ir.access.csv`.
- Tests: add `_test_user_groups = None` to the `BaseCommon` test class.

Migration changes only (diff after the pre-commit auto fixes): https://github.com/<user_org>/<repo>/pull/<n>

Assisted-by: Claude Code (claude-opus-5-5)
```

To change a PR afterwards, `gh pr edit` may fail with a GraphQL "Projects (classic) is being
deprecated" error — use the REST API instead:
```bash
gh api -X PATCH repos/<user_org>/<repo>/pulls/<n> -F body=@<body.md> --jq .html_url
```

**PR against OCA** — only on explicit request. Keep the fork review PR open and its
`20.0-mig-<module>-base` branch pushed, so the link in the body keeps working:
```bash
gh pr create -R OCA/<repo> --base 20.0 --head <user_org>:20.0-mig-<module> \
    --title "[20.0][MIG] <module>: Migration to 20.0" --body-file <body.md>
```

## Other notes

- Remote URLs (e.g. in a doodba `repos.yaml`) can contain GitHub tokens: never print them (mask
  `ghp_...` in any output) and point the user to rotating them if one leaked.
- Report the branch the clone was on before (e.g. `20.0`) so the user can switch back.
