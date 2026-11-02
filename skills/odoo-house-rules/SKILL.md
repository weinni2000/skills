---
name: odoo-house-rules
description: >-
  Opinionated house rules for writing custom Odoo addons (Odoo 17-20): file
  naming per model, manifest versioning, field and variable naming
  (`_id`/`_ids`, `calculated` for computed fields), model layout, constraints,
  translations, view inheritance, hooks and method overrides, SCSS/JS
  pitfalls, migrations, and the checks to run before calling work done. Use
  when writing, refactoring or reviewing code in a custom (non-core) Odoo
  addon.
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

## Before calling it done

- Read `.pre-commit-config.yaml` and run `pre-commit run --files <changed files>` (stage them first:
  pre-commit stashes unstaged changes). Re-stage hook fixes and rerun until every hook passes.
  Never skip hooks or add suppressions just to pass.
- Required manifest metadata (e.g. `website` checked by `oca-fix-manifest-website`) is present.
- `README.rst` renders: headings underlined at least as long as the title.
- Update/install the module on the database the running server uses and check
  `ir_module_module.state`; for assets, check the page actually loads the new bundle.
- Stage only your own changes; never commit generated logs or debug output.
