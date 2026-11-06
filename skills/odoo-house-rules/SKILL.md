---
name: odoo-house-rules
description: >-
  Opinionated house rules for writing custom Odoo addons (Odoo 17-20): file
  naming per model, manifest versioning, field and variable naming
  (`_id`/`_ids`, `calculated` for computed fields), model layout, constraints,
  translations, view inheritance, hooks and method overrides, SCSS/JS
  pitfalls, migrations, SonarQube findings, and the checks to run before
  calling work done. Use when writing, refactoring or reviewing code in a
  custom (non-core) Odoo addon.
---

# Odoo house rules

Rules for custom addons, collected from real review feedback and failed installs. They are
deliberately opinionated: some deviate from Odoo's core guidelines (e.g. `_id` on recordset
variables). Where they conflict with `odoo-guidelines`, these win in repositories that adopt them;
in OCA repositories, OCA conventions win (see "OCA repositories" below). Follow the surrounding
file's style when it consistently does something else.

## Files and module structure

- One model per Python file in `models/`, named after the model: `res.company` → `res_company.py`.
  Never `models.py`.
- Views, actions and menus of a model go in `views/<model_name>_views.xml` (e.g.
  `product_attribute_views.xml`). One file per model, never a feature-named file, never two models
  in one file. Append to the existing file if there is one.
- Data records go in `data/<model_name>_data.xml` (e.g. `res_company_data.xml`), same rule.
- `models.TransientModel` wizards live in `wizards/` with its own `wizards/__init__.py`, not in
  `models/`.
- Access rights go into the single `security/ir.model.access.csv` (Odoo 20:
  `security/ir.access.csv`); no extra ACL CSV files.
- `pre_init_hook` / `post_init_hook` / `uninstall_hook` live in `hooks.py` at the module root and
  are imported in `__init__.py`. No `__all__` in `__init__.py`.
- New modules ship `README.rst` (at least the title) and OCA-style `readme/` fragments:
  `DESCRIPTION.md`, `CONFIGURE.md` (if configuration is needed), `CONTRIBUTORS.md`.
- Constant dicts/lists go at module level after `_logger`, not as class attributes. Longer than
  ~20 lines → move them to `_const.py` in the same package.

## Manifest

- Bump the patch version of every module you change (`19.0.1.7` → `19.0.1.8`).
- New modules start with a version ending in `.1` (`19.0.1.0.1`, not `19.0.1.0.0`).

## Python

- Recordset variables end with `_id` / `_ids`: `account_id = self.env["account.account"].search(...)`.
  Loop variable over a generic recordset (server actions, `for record in self`): `record`; a typed
  item from a plural collection may mirror it (`for line_id in line_ids:`).
- Never `print()`; use `_logger = logging.getLogger(__name__)`.
- Log level by meaning: `_logger.warning` is fine in OCA, but a CI with checklog
  (`OCA_ENABLE_CHECKLOG_ODOO`) fails the tests on any unexpected warning. Expected situations, such
  as a record without the external ID to look up (e.g. no Wikidata QID), log at `info` or `debug`;
  `warning` only for something an admin has to fix. A test that triggers a real warning on purpose
  wraps it in `self.assertLogs(logger, "WARNING")`.
- Imports at the top of the file, never inside a function.
- String formatting: untranslated strings use f-strings (ruff UP031). Escape quotes with `\"`, never
  typographic quotes.
- Translated strings use named placeholders and a mapping, never extra arguments to `_()`:
  `_("No tax on lines: %(lines)s") % {"lines": names}`. With pylint_odoo (`translation-not-lazy`,
  `prefer-env-translation`), translate into a variable first:
  ```python
  message = self.env._("Created %(count)s lines.")
  message = message % {"count": count}
  ```
- Never use `_` as a throwaway variable (it shadows the translation function, F823). Use
  `_unused`, `_attachments`, ...
- Never `cr.commit()` in module code; use `flush_*` / `invalidate_*` when you need consistency
  inside the transaction.
- `search([])` that really needs all records: keep it and add
  `# pylint: disable=no-search-all`.

## Models and fields

- Underscore attributes (`_name`, `_description`, `_inherit`, `_rec_name`, `_order`, constraints)
  first, then all `fields.*` declarations, then methods. Never declare a field after a method.
- Every new model defines `_description`.
- AbstractModel mixins: `_name` ends in `.mixin`, file ends in `_mixin.py`.
- Relational fields end in `_id` (Many2one) or `_ids` (One2many/Many2many). When renaming, update
  related/compute paths, domains, `@api.depends`, views and `vals` keys.
- Computed and related fields carry `calculated` in the technical name
  (`event_count_calculated`); the label stays plain (`string="Events"`), no "(Calculated)".
- Don't add `string=` that only repeats the auto-generated label (pylint W8113) — neither on the
  field nor in a view.
- Constraints: never `_sql_constraints`; use
  `_my_model_code_uniq = models.Constraint("unique(code)", "Code must be unique.")`.
- When splitting a `_compute_x` into helpers, `@api.depends(...)` stays on `_compute_x`.

## Overrides

- With `_inherit`, always call `super()`; never reimplement a parent method from scratch. To
  suppress parent behaviour, call `super()` with adjusted context and post-process the result.
- Context with super: `super(MyClass, self.with_context(...))._method()`, never
  `super(MyClass, self).with_context(...)._method()` (infinite recursion).
- A *complete* replacement of another module's method (rare, last resort): monkey-patch in
  `hooks.py` at import time:
  ```python
  from odoo.addons.<module>.models.<file> import <Class>

  def _method(self):
      ...

  <Class>._method = _method
  ```

## Views and XML

- Odoo 18+: `<list>` and `view_mode="list,form"`, never `tree`.
- Inheritance: locate by `name`, `id` or xpath on `@name` — never `string` (neither
  `<group string="Foo" position="...">` nor `[@string='...']`). If the target has no `name` and you
  own the source view, add one there.
- Inheriting `<template>`: reuse the inherited id (`id="contact_name"` for
  `inherit_id="base.contact_name"`).
- Odoo 19+ search views: group-by options are plain
  `<filter name="..." context="{'group_by': 'field'}"/>` nodes, not wrapped in
  `<group string="Group By">` / `expand=`. Validate arches against `base/rng/<type>_view.rng` for
  the real error.
- Prefer `invisible` over `column_invisible` in list/one2many views (breaks with child-field refs
  in 18/19); ask before using it.
- Odoo 19: `ir.actions.server` has no `groups_id`; guard in Python (`_check_group()`) instead.

## Web assets

- Every user-facing JS string goes through `_t()`, with named placeholders
  (`_t("Could not save: %(detail)s", {detail})`), never template literals. No English inside
  `t-att-*` expressions — move it into a method returning `_t(...)`. See `odoo-translations`.
- SCSS: no native CSS `min()` / `max()` / `clamp()` (libsass treats them as Sass functions and the
  whole bundle fails). Use two properties: `width: calc(100vw - 24px); max-width: 480px;`.
- SCSS colors from the theme: `$primary`, `$secondary`, `o-color(...)`, tints via
  `mix($primary, #fff, 12%)` — no hard-coded brand hex values.
- ESLint `init-declarations`: `let handle = null`, not bare `let handle`.
- No `alert()`; use the notification service.

## Migrations

- Migration scripts: `migrations/<manifest version>/pre-migrate.py` / `post-migrate.py` with
  `def migrate(cr, version)`; get an env with `api.Environment(cr, SUPERUSER_ID, {})`. Don't
  import `registry` (gone in Odoo 19).
- `noupdate="1"` data isn't reloaded by an update: change existing records in a migration script.

## OCA repositories

- Manifest version for a migrated/new module is `<odoo>.1.0.0` (OCA convention beats the `.1` rule).
- Don't touch `readme/CREDITS*` or add contributors unless asked.
- See `oca_migration_git` / `oca_pr_checks` for the git flow.

## SonarQube

Patterns SonarQube reported in custom addons. Write the code so they don't come up.

- No credentials in code or data files, not even demo passwords or keys in standalone scripts
  (S2068, S7013): read them from an untracked `.env` / the environment; without a value, skip the
  step instead of falling back to a literal.
- No debug switches: `if True:`, `if False:`, `if x or True:`, `flag = True` followed by
  `if flag:` (S5797). Delete the dead branch and keep the code that runs.
- No dead stores (S1854): don't assign a value that is overwritten before it is read
  (`width = int(w * 1.3)` followed by `width = 832`), no self-assignments (S1656), no statements
  without effect such as `"".join(...)` or `a / b` on their own (S905, S2201). Chains of
  alternatives use `if/elif/else`: `if a: … if b: … else: …` overwrites the result of `a`.
- No duplicate branches: the same condition twice in an `elif` chain (S1862), `if/else` with
  identical bodies (S3923), duplicate keys in an object/dict literal (S1534) — only the last one
  counts.
- An empty function says why in a comment (registered hook, form button that only saves, disabled
  feature) or is deleted when nothing uses it (S1186).
- `except`: don't list a class next to its parent (S5713). `OSError` already covers `URLError`,
  `TimeoutError` and `requests.RequestException`.
- lxml on files or downloads: `etree.XMLParser(resolve_entities=False, no_network=True)` (S2755).
- Logging: arguments match the placeholders, `_logger.warning("Skipped %s: %s", name, error)`
  (S3457); never `_logger.warning(...) % {...}`. Log messages are not translated.
- NaN: `math.isnan(value)`, not `value != value` (S1764).
- JS: `forEach` when the result of `map` isn't used (S2201); `replaceAll()` for global regexes
  (S7781); `sort((a, b) => a.localeCompare(b))` for strings (S2871); `await` only on async
  functions — make placeholder methods `async` (S4123); keep a variable's type stable (`0`, not
  `false`, for "no error code"; S3403).
- JS, more: arrays only used with `includes()` are a `Set` (S7776); `a?.b` instead of `a && a.b`
  (S6582, mind value positions: `a && a.b` returns `a`); arrow functions instead of
  `const self = this` (S7740) — but keep a `function` whose own `this` matters (Leaflet control
  methods, functions called as methods of a returned API object); `"x".replaceAll("&", ...)` with
  a string instead of a one-character regex; `.at(-1)`; `node.remove()`; `Object.hasOwn()`; one
  `push(a, b)` instead of two pushes; `null`, not `false`, for "no value" in plain JS helpers.
- Python, more: no nested `if a:` + `if b:` without else (S1066), `!=` instead of `not a == b`
  (S1940), no `continue` at the end of a loop body or before `elif` (S3626), no nested
  conditional expressions (S3358), `{x for ...}` instead of `set(x for ...)` (S7494), no
  `if x: pass else: ...` (S108) — invert the condition; `raise ValueError(...) from error`, not
  `raise Exception(...)` (S112). A parameter that is overwritten before it is read is removed
  or gets a differently named local (S1226).
- Regex: no `^a|b$` (S5850) — two `re.sub()` calls, one per anchor; `\d` instead of `[0-9]`;
  no group around a whole pattern (S6395). Generate long alternations from the mapping that
  interprets the match (`"|".join(sorted(MONTHS, key=len, reverse=True))`), so they can't drift.
- No sync file IO in `async` functions (S7493); debug dumps to fixed paths don't belong there at
  all.
- Don't commit copies (`* copy.js`, `*_old.py`): they are analysed like real code.

Suppressions:

- `# NOSONAR(<rule>)` (`// NOSONAR`) only for a false positive or an Odoo pattern, with the reason
  in a comment. When the line already has a linter exception for the same thing, add it as its own
  comment in front of it, `def sitemap_forum(env, rule, qs):  # NOSONAR(S5720)  # noqa: B902`
  (Odoo calls sitemap functions without `self`). `# noqa: B902 NOSONAR` is invalid syntax (S7632)
  and suppresses nothing.
- Rules that don't apply to Odoo go into `sonar.issue.ignore.multicriteria` in
  `sonar-project.properties`, with the reason in a comment **on its own line**: `.properties` files
  have no inline comments, `ruleKey=python:S1481 # reason` silently never matches. Ignored with
  reason: S1172 (Odoo fixes the signatures of `migrate`, hooks, overrides, routes), S100 (Odoo /
  unittest method names), S6890 (Odoo uses `pytz`), S6903 (Odoo datetimes are naive UTC), S3776
  (already ruff C901), commented-out code S125 (already ruff ERA),
  S7785 (no top-level `await` in Odoo JS modules, they are transpiled into `odoo.define()`).
- Known false positives, NOSONAR with reason: S7729 on Leaflet's `L.map()`; S7784 on
  `JSON.parse(JSON.stringify(x))` of an Owl `reactive` proxy (`structuredClone()` throws on
  proxies); S7760 when Odoo can send `false` (a default parameter only covers `undefined`);
  S6019 on a lazy quantifier followed by `(?:…|$)`; S5857 when `[^}]*` would break on nested
  JSON; S7503 on an async test mock. Test such regexes before calling them false positives.
- NOSONAR goes on the reported line itself. prettier and ruff-format move a trailing comment of a
  wrapped statement onto its own line, where it suppresses nothing: restructure the statement so
  it fits on one line (a small helper function, a separate `setView()` call, adjacent string
  literals in Python) and check `git diff | grep "^+\s*// NOSONAR"` after formatting.
- Exclude third-party or vendored code (`sonar.exclusions`) instead of changing it: third-party
  modules, `libs/`, minified or generated files, copied stylesheets (Leaflet, Esri), code derived
  from upstream projects.

## Before calling it done

- Read `.pre-commit-config.yaml` and run `pre-commit run --files <changed files>` (stage them first:
  pre-commit stashes unstaged changes). Re-stage hook fixes and rerun until every hook passes.
  Never skip hooks or add suppressions just to pass.
- Required manifest metadata (e.g. `website` checked by `oca-fix-manifest-website`) is present.
- `README.rst` renders: headings underlined at least as long as the title.
- Update/install the module on the database the running server uses and check
  `ir_module_module.state`; for assets, check the page actually loads the new bundle.
- Stage only your own changes; never commit generated logs or debug output.
