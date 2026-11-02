# Odoo agent skills

Agent skills (Claude Code, Codex, and other agents that read `SKILL.md`) for Odoo and OCA work.

| Skill | What it does |
| --- | --- |
| [`oca_migration_git`](skills/oca_migration_git/SKILL.md) | OCA-style module migration (default 19.0 → 20.0): replay the history with `git format-patch \| git am`, squash bot commits, pre-commit commit, `[MIG]` commit, review PR in your fork. Includes a list of Odoo 20 changes seen in real migrations. |
| [`oca_pr_checks`](skills/oca_pr_checks/SKILL.md) | Read failing OCA CI checks of a PR, reproduce them locally, fix and amend into the `[MIG]` commit. |
| [`odoo-translations`](skills/odoo-translations/SKILL.md) | Find strings that can't be translated (JS without `_t()`, `t-att-*` expressions, …), fix them, export the POT, write the `.po`, verify. Ships a scanner script. |
| [`odoo-house-rules`](skills/odoo-house-rules/SKILL.md) | Opinionated rules for custom addons: file per model, naming (`_id`/`_ids`, `calculated` for computed fields), model layout, overrides, view inheritance, SCSS/JS pitfalls, checks before calling work done. |
| [`doodba`](skills/doodba/SKILL.md) | How to do those steps in a [Doodba](https://github.com/Tecnativa/doodba-copier-template) project: `repos.yaml` / git-aggregator, `addons.yaml`, `click-odoo-update`, tests, translations. |

The first three skills don't depend on a particular setup. They use plain `git`, `gh`,
`pre-commit` and `odoo-bin`. When available, they also use:

- [odev](https://github.com/odoo-odev/odev) for fresh test databases and `upgrade-code`.
- the `doodba` skill, if your code lives in a Doodba project.

Skip `doodba` if you don't use Doodba.

## Install

With the [skills CLI](https://github.com/vercel-labs/skills):

```bash
npx skills add weinni2000/skills                        # pick skills interactively
npx skills add weinni2000/skills@oca_migration_git      # a single skill
```

Or by hand, by copying or symlinking a skill folder into your agent's skills directory:

```bash
git clone https://github.com/weinni2000/skills.git
ln -s "$PWD/skills/skills/oca_migration_git" ~/.claude/skills/oca_migration_git
```

## Recommended companion skills

These skills mention the following ones, but don't need them:

- `odoo-guidelines`, `odoo-web-guidelines`, `odoo-review`, `odoo-security`: Odoo SA's house
  rules, in the [`skills/`](https://github.com/odoo/odoo/tree/master/skills) folder of `odoo/odoo`
  (master).
- `odoo_upgrade_skill`, `odoo_upgrade_utils`, `odev`, `odoo_commit_message_guidelines`: from
  [odoo-ps/ps-ai-skills](https://github.com/odoo-ps/ps-ai-skills)
  (`npx skills add odoo-ps/ps-ai-skills`).

## Opinionated defaults

These skills make some workflow choices. Edit the `SKILL.md` if yours differ:

- All your own migration changes go into one `[MIG]` commit. Follow-up fixes are amended into it
  and force-pushed.
- Every migration gets a review PR in your fork (base branch → migration branch). A PR against OCA
  is only opened on request.
- The skills never add tests just to raise coverage.
- `readme/CREDITS` and `readme/CONTRIBUTORS` are left unchanged.
- AI-assisted commits and PRs end with an `Assisted-by: <agent> (<model>)` trailer.
