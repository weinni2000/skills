---
name: odoo-translations
description: >-
  Make an Odoo module translatable and translate it (default German, de.po):
  scan for user-facing strings that bypass translation (JS literals without
  _t(), _t() inside HTML template literals, English inside t-att-*
  expressions, Python exceptions without _()), fix them, export the POT from
  Odoo, merge it into i18n/<lang>.po and fill only the msgstr with a checker
  that keeps placeholders and markup intact, then verify Odoo serves the
  translations. Use whenever a change adds or changes user-facing strings
  (labels, help, _t()/_() texts, view text), when a module shows English on a
  translated site, when asked to add/update translations or an i18n folder,
  or before publishing a module. Never write .po entries by hand.
---

# Odoo module translations

Translations fail silently: an untranslatable string just stays English. The
work is therefore two halves, in this order: make every visible string
translatable, then export and translate. Exporting first only yields a
complete-looking `.po` that misses whatever the code hides from the export.

The `.po` file is Odoo's output, not yours: always export it from Odoo, then
translate only the `msgstr` values (steps 3-4). This also applies to a single
new string added while working on something else.

The target language defaults to German (`de`); use another one when the user
asks.

## 1. Scan

```bash
python3 <this skill's directory>/scripts/find_untranslated.py <module_path>
```

Categories reported (heuristic, review each hit; technical strings can be
ignored):

| Category | Problem |
| --- | --- |
| `js-literal` | Visible JS string without `_t()` (notifications, dialog titles, labels, placeholders, default names) |
| `js-html` | English text or `title`/`aria-label`/`placeholder` inside HTML built in JS (`innerHTML`) |
| `js-t-in-template` | `_t()` inside an HTML template literal: works at runtime, but the export never extracts it |
| `js-template-lit` | `_t(`...${x}`)`: the key changes per value, never matches a translation |
| `xml-att-expr` | English inside a `t-att-*`/`t-attf-*` expression in an Owl template: not extracted |
| `py-exception` | `raise UserError("...")` and friends without `_()` |
| `py-format-in-t` | `_(f"...")` or `_("..." % x)`: formatted before the lookup, never matches |

Also check by eye what a regex cannot see: strings built by concatenation,
labels in JS objects passed around, `Markup` in Python.

## 2. Fix

JavaScript (`import {_t} from "@web/core/l10n/translation"`):

```js
// literal -> _t()
this.notification.add(_t("Map is not available on this page."), {type: "warning"});
// values: named placeholders, never template literals
_t("Could not save this custom area: %(detail)s", {detail});
// HTML built in JS: translate into variables FIRST, escape, then interpolate.
// _t() written inside the template literal is NOT picked up by the export.
const cancelLabel = htmlEscape(_t("Cancel"));          // htmlEscape from "@odoo/owl"
bar.innerHTML = `<button title="${cancelLabel}" aria-label="${cancelLabel}">...</button>`;
```

Owl templates (`static/src/**/*.xml`): plain text and static attributes
(`title="..."`, `placeholder="..."`) are extracted automatically. English
inside an expression is not:

```xml
<!-- bad -->  <button t-att-title="this.hasMap ? '' : 'Map is not available'"/>
<!-- good --> <button t-att-title="this.getMapTitle()"/>
```
```js
getMapTitle() { return this.hasMap ? "" : _t("Map is not available on this page."); }
```

Python: follow the house rule of the repository. In OCA-style repositories
(pylint_odoo `translation-not-lazy`), translate the literal first and format
after the lookup:

```python
message = self.env._("Folio %(name)s cannot be modified")
raise UserError(message % {"name": folio.name})
```

Field labels, selection values, view arch text and data record names are
exported from the database, not the code, so the module must be up to date in
the DB.

Lint the touched files (`pre-commit run --files ...`) and re-run the scanner
until it is clean or every remaining hit is a justified technical string.

## 3. Export the POT from Odoo

**Never write `.po` entries by hand** — not even "just this one new string".
Every entry (msgid, `#. module:` / `#. odoo-javascript` comments, `#:`
references, model/field keys) comes from Odoo's export; a hand-made entry
misses or misnames them, and Odoo then ignores it or the next export
rewrites it. Your part is only the `msgstr`.

The module must be installed and up to date in the database: field labels,
selection values, view arch and data are exported from the DB, so update the
module first (`-u <module>`, `click-odoo-update`, ...) after changing them.
JS/Owl template strings are read from the files.

```bash
# Odoo 19+: to a file, without touching the module folder
odoo-bin i18n export -c <odoo.conf> -d <db> -l pot -o /tmp/<module>.pot <module>
# Odoo <= 18
odoo-bin -c <odoo.conf> -d <db> --modules=<module> \
  --i18n-export=/tmp/<module>.pot --stop-after-init
# doodba: see the doodba skill ("Translations")
```

Without `-o`, `i18n export` writes `<module>/i18n/<module>.pot` itself; keep
that file up to date too if the module ships one. odev has no translation
command; `odev-plugin-ai-translation` overwrites the target `.po`, so never
point it at a translated `.po`.

## 4. Merge, then translate only the msgstr

Use the bundled `scripts/po_tool.py` (needs `polib`, which Odoo depends on):

```bash
T=<this skill's directory>/scripts/po_tool.py
python3 $T merge <module>/i18n/de.po /tmp/<module>.pot   # creates de.po if missing
python3 $T todo  <module>/i18n/de.po > /tmp/todo.json
# fill the empty values in /tmp/todo.json ("_context" says where each term comes from)
python3 $T fill  <module>/i18n/de.po /tmp/todo.json
msgfmt --check -o /dev/null <module>/i18n/de.po
```

- `merge` keeps existing translations, adds the new terms empty, drops terms
  no longer exported, sets `Language`/`Plural-Forms` on a new file, and
  writes the file the way Odoo does (polib, 78 columns), so the diff shows
  only real changes. Prefer it to `msgmerge`: `msgmerge --no-wrap` rewraps
  the whole file and adds an empty `"Language: \n"` header.
- `todo` leaves out the module description (README/index.html) and **texts
  for the language model** (`ai_tool_description`, prompts, instructions):
  translating those changes what an AI agent does. Pass `--include-readme` /
  `--include-llm` only when the user asks.
- `fill` writes only empty or fuzzy `msgstr` and refuses a translation whose
  system syntax differs from the msgid, writing nothing:
  - placeholders identical: `%(name)s` keeps the English name (never
    `%(kategorie)s`), same `%s` / `%%` / `{x}` count;
  - markup identical: view terms contain tags, e.g.
    `<span class="col-lg-2">levels</span>` → `<span class="col-lg-2">Stufen</span>`;
    translate text between tags only, never attributes or `t-*` expressions;
  - same leading/trailing whitespace and line breaks (multi-line terms
    keep their `\n`);
  - a term that is not in the `.po` is reported: export again, don't add it.
- Only fill the values of `todo.json`; never retype a key: it must be the
  exact msgid, including spaces, quotes and line breaks.
- Translation style: follow the existing `.po` (e.g. informal "du" vs
  "Sie", established terms like "Veranstaltung" for event); strings already
  in the target language keep `msgstr` = `msgid`.

No manifest change is needed: Odoo loads every `.po` in `i18n/`. Bump the
module's version if the repository's rules ask for it.

## 5. Load and verify

- Model terms (field labels, views, data) live in the database: update the
  module so the `.po` is loaded into it.
- JS/template terms are read from the `.po` files and cached per process:
  **restart the server after the update** — a module update alone can keep
  serving the old frontend translations (seen on Odoo 20).
- Verify in `odoo-bin shell` (the HTTP route may 404 for anonymous curl):

```python
mods = env["ir.http"]._get_translations_for_webclient(["<module>"], "de_DE")[0]
{m["id"]: m["string"] for m in mods["<module>"]["messages"]}
```

  or on a website page, the payload of `/website/translations?lang=de_DE`
  must contain the new terms.

Report what was untranslatable, what was fixed, the number of translated
terms, and anything left in English on purpose.

## Traps seen in practice

- Strings like "or" / "Cancel" can look translated while the module has no
  `i18n/` at all: frontend terms are matched by source text across all
  modules, so core's translations leak in. Do not conclude a module is
  translated from a few translated words.
- `_t()` inside `${...}` of an HTML template literal is invisible to the
  export (verified on Odoo 20): the string stays English forever.
- A `title`/label typed by the user is data, not a term: never wrap stored
  record values in `_t()`.
- Odoo <= 18: `trans_export(lang, modules, buffer, format, cr)` takes a
  cursor; from 19 it takes an `env`. Scripts calling it directly break across
  versions — prefer the CLI.
- A hand-written `.po` entry looked fine but had no `#. odoo-javascript`
  comment / wrong reference: export from Odoo instead (step 3).
- A frontend RPC without `lang` in its context searches translated names in
  English (e.g. `name ilike "lauf"` misses the category "Laufsport" whose
  English name is "Running"). Not a `.po` problem: pass the page language
  (`document.documentElement.lang`) in the context of such searches.
