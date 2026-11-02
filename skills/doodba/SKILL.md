---
name: doodba
description: >-
  Work inside a Doodba project (Tecnativa doodba-copier-template): where to edit
  code, getting repos and unmerged PRs with git-aggregator (repos.yaml,
  addons.yaml), updating/installing modules with click-odoo-update, running
  tests, shell and SQL in the containers, exporting translations. Use when the
  cwd or the module lives under `<project>/odoo/custom/src/` next to a
  `repos.yaml`, or when another skill (oca_migration_git, oca_pr_checks,
  odoo-translations) needs the doodba way of doing a step.
---

# Working in a Doodba project

A Doodba project is recognised by `tasks.py`, `devel.yaml`, `.copier-answers.yml` at the root and
`odoo/custom/src/repos.yaml` + `addons.yaml`. Run `docker compose` / `invoke` from the project root;
run `gitaggregate` from `odoo/custom/src`.

Before acting, read the project's own facts instead of assuming them: the Odoo version
(`.copier-answers.yml` → `odoo_version`), the DB name (`PGDATABASE` in `devel.yaml`/`.env`, usually
`devel`), the exposed ports (`devel.yaml`), and the available tasks (`invoke --list`).

## Layout

| Path                              | What                                                         |
| --------------------------------- | ------------------------------------------------------------ |
| `odoo/custom/src/<repo>`          | aggregated git clones — edit code here                       |
| `odoo/custom/src/private`         | project's own addons (always on the addons path)             |
| `odoo/custom/src/repos.yaml`      | which remotes/branches/PRs git-aggregator merges per repo    |
| `odoo/custom/src/addons.yaml`     | which addons of each repo are linked into the addons path    |
| `odoo/auto/addons`                | generated symlinks — never edit                              |
| `devel.yaml` / `prod.yaml` / `test.yaml` | compose files per environment                         |

- A module only loads if its repo **and** the module (or `"*"`) are listed in `addons.yaml`. A new
  repo or module that "is not found" is usually missing there.
- The devel stack usually mounts `odoo/custom/src` read-write and runs Odoo with
  `--dev=reload,...`: pure Python edits reload by themselves; field/view/data changes need an update.
- Prod/test stacks (`-f prod.yaml`, `-f test.yaml`, other `-p` project names): never touch them
  without asking.

## Dev stack

```bash
invoke start            # or: docker compose up -d
invoke restart          # or: docker compose restart odoo
invoke logs             # or: docker compose logs -f odoo
invoke stop
```

`export DOODBA_UMASK=0022` silences the umask warning of `docker compose`.

## Install / update modules

Update after a field/view/data change — `click-odoo-update` only updates modules whose checksum
changed:
```bash
docker compose stop odoo
docker compose run --rm --no-deps odoo click-odoo-update
docker compose up -d odoo
```
Install a new module: `invoke install --modules=<module>` (stops odoo; start it again afterwards),
or `docker compose run --rm odoo odoo -i <module> --stop-after-init`.

Verify in the DB rather than trusting the log:
```bash
docker compose exec -T db psql -U odoo -d devel \
  -c "select name, state, latest_version from ir_module_module where name = '<module>'"
```

Data files with `noupdate="1"` are not reloaded by an update: changing existing records needs a
`migrations/<version>/post-migrate.py`.

## Shell, SQL and other odoo-bin commands

`odoo-bin` lives in the container as `odoo`; every `odoo-bin <command>` from another skill runs as
`docker compose run --rm odoo odoo <command>`, with paths as seen inside the container
(`/opt/odoo/custom/src/<repo>`):

```bash
docker compose run --rm odoo odoo shell          # env is available
docker compose exec -T db psql -U odoo -d devel -c "..."
# code rewrites for a version jump (needs the devel stack's read-write src mount)
docker compose run --rm odoo odoo upgrade_code --from 19.0 \
  --addons-path /opt/odoo/custom/src/<repo> --glob '<module>/**/*' --dry-run
```

## Tests

- `invoke test --modules=<a>,<b> [--tags=/<a>:TestClass.test_x]` runs in the **dev DB** (installs or
  updates the modules there). Restart odoo afterwards (`invoke restart`).
- On a separate, fresh DB (keeps the dev DB untouched):
  ```bash
  docker compose run --rm odoo odoo -d <module>_test -i <module> \
    --test-enable --test-tags /<module> --stop-after-init --workers=0
  ```
- `invoke resetdb --dbname=<db> --modules=<m>` **drops and recreates** a DB — never on `devel`
  without asking.
- odev (optional) can run on the host against the same clone: pass `<project>/odoo/custom/src/<repo>`
  (and dependency repos) as addons paths.

## Translations

- `invoke updatepot --module=<module>` runs `click-odoo-makepot` in the container: writes the POT
  and merges it into existing `.po` files (`--repo=<repo>` for a whole repo). It stops odoo.
- Alternative (Odoo 19+): `docker compose run --rm odoo odoo i18n export -d devel <module>`.
- After adding a `.po`: update the module (model terms) and restart (JS terms are cached).

## Getting code: git-aggregator

`repos.yaml` is the source of truth for every clone in `odoo/custom/src`. Bring branches, forks and
unmerged PRs in through it — never by `git clone` by hand or by copying modules into temp folders,
or the next aggregation silently drops them.

```bash
invoke git-aggregate                         # all repos, inside the devel-setup container
# a single repo, from odoo/custom/src on the host (gitaggregate may not be on PATH: ~/.local/bin)
gitaggregate -c repos.yaml --expand-env --env-file .env -d <repo>
```

- Aggregation checks out and **rebuilds** the `target:` branch of the clone: commit/push work on
  other branches first, and switch back to the branch you were on afterwards if needed.
- The remote of a repo is named after its key in `repos.yaml` (e.g. `account-invoicing`), not
  `origin`.
- Aggregation aborts when a remote in `target:`/`merges:` has no branch of that name (e.g.
  `fatal: couldn't find remote ref 20.0`). If it is the user's own fork, create the branch as an
  exact copy of upstream (`git push <user_org> <upstream_remote>/20.0:refs/heads/20.0`) and tell
  the user; don't edit `target:` without asking.
- Remote URLs can contain tokens: pipe output through `sed -E 's/gh[po]_[A-Za-z0-9]+/gh*_***/g'`
  and never print them.

### Migration branches and dependency PRs

Add a migration branch (or any branch under test) to its repo's `merges:` using the user's fork
remote, appended after the existing merges; add the remote to `remotes:` if missing. Unmerged
**dependency PRs** go **before** it, using the PR author's remote + branch, with the PR ref as a
comment, so the aggregated checkout is runnable:

```yaml
./connector:
  remotes:
    connector: https://github.com/OCA/connector.git
    <user_org>: git@github.com:<user_org>/connector.git
    ForgeFlow: https://github.com/ForgeFlow/connector.git
  target: <user_org> $ODOO_VERSION.local
  merges:
    - connector $ODOO_VERSION
    - ForgeFlow 20.0-mig-component # connector refs/pull/540/head
    - ForgeFlow 20.0-mig-component_event # connector refs/pull/541/head
    - <user_org> 20.0-mig-connector
```

- PR remote/branch: `gh pr view <n> -R OCA/<repo> --json headRepositoryOwner,headRefName`; check it
  exists with `git ls-remote <url> <branch>`.
- Check the merges are conflict-free on a throwaway branch first (`git checkout -b tmp-agg-check
  <oca_remote>/20.0`, `git merge` each in order, then delete it and switch back).
- Dependencies from another repo (e.g. `queue_job` in `./queue`) need their entry on the target
  version too — ask before changing a pinned entry.
- A branch must be pushed to the fork before aggregation can fetch it.

Test loop for a branch that needs dependency PRs:
1. Commit on the working branch and push it to the fork.
2. Add the dependency PRs and the branch to `merges:` (above).
3. `gitaggregate ... -d <repo>` → the clone is on the aggregated target branch with everything.
4. Install/test (see "Tests").
5. Fix on the working branch, amend/commit, push, re-aggregate, test again. Say at the end which
   branch the clone is on.

## Pre-commit

`invoke git-aggregate` installs the pre-commit hooks of each repo that has a
`.pre-commit-config.yaml`. Run `pre-commit run --files <files>` inside the repo (stage files first:
pre-commit stashes unstaged changes); `invoke lint` runs the project-level hooks.
