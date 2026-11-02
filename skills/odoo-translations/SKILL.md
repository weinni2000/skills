---
name: odoo-translations
description: >-
  Make an Odoo module translatable and translate it (default German, de.po):
  scan for user-facing strings that bypass translation (JS literals without
  _t(), _t() inside HTML template literals, English inside t-att-*
  expressions, Python exceptions without _()), fix them, export the POT,
  create or merge i18n/<lang>.po, and verify Odoo serves the translations.
  Use when a module shows English on a translated site, when asked to
  add/update translations or an i18n folder, or before publishing a module.
---

# Odoo module translations

Translations fail silently: an untranslatable string just stays English. The
work is therefore two halves, in this order: make every visible string
translatable, then export and translate. Exporting first only yields a
complete-looking `.po` that misses whatever the code hides from the export.

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

## 3. Export the POT

The module must be installed in the database, and up to date: if Python model
strings changed, update the module first (`-u <module>`, `click-odoo-update`,
or whatever the user's setup uses). JS/XML template strings are read from
files.

```bash
# Odoo 19+
odoo-bin i18n export -c <odoo.conf> -d <db> <module>
# Odoo <= 18
odoo-bin -c <odoo.conf> -d <db> --modules=<module> \
  --i18n-export=<module_path>/i18n/<module>.pot --stop-after-init
# doodba: see the doodba skill ("Translations")
```

`i18n export` writes `<module>/i18n/<module>.pot`; `-l de_DE` exports the
terms already translated in the DB instead of an empty template. odev has no
translation command; `odev-plugin-ai-translation` exists but overwrites the
target `.po` file, so never point it at a hand-made `.po`.

## 4. Create or merge <lang>.po

- **New file**: copy the POT to `i18n/de.po`; in the header set
  `"Language: de\n"`, `"Plural-Forms: nplurals=2; plural=(n != 1);\n"`,
  and `"Last-Translator: ..."` (ask the user or take the module author).
- **Existing file**: keep the translations and add the new terms with
  `msgmerge --quiet --update --no-fuzzy-matching --backup=none de.po <module>.pot`.
- Translate every `msgstr`. Keep placeholders (`%(detail)s`, `%s`) and
  trailing punctuation/spacing exactly; strings already in the target
  language keep `msgstr` = `msgid`. Leave the module's own
  summary/description empty only if they are placeholders.
- Check: `msgfmt --check --statistics -o /dev/null de.po` and
  `msgattrib --untranslated de.po | grep '^msgid'` (only the header should
  remain).

No manifest change is needed: Odoo loads every `.po` in `i18n/`. Bump the
module's version if the repository's rules ask for it.

## 5. Load and verify

- JS/template terms are read from the `.po` files at runtime and cached:
  restart the server.
- Model terms (field labels, views, data) live in the database: update the
  module so the new `.po` is loaded into it.
- Verify in `odoo-bin shell` (the HTTP route may 404 for anonymous curl):

```python
mods = env["ir.http"]._get_translations_for_webclient(["<module>"], "de_DE")[0]
{m["id"]: m["string"] for m in mods["<module>"]["messages"]}
```

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
