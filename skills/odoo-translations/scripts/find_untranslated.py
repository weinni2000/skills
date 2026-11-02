#!/usr/bin/env python3
"""Find user-facing strings in an Odoo module that cannot be translated.

Usage: find_untranslated.py <module_path> [<module_path> ...]

Reports, as file:line [category] snippet:
  js-literal      JS string shown to users without _t()
  js-html         English text/attributes inside HTML built in JS (innerHTML)
  js-template-lit _t() around a template literal (`...${x}`), never matches
  js-t-in-template _t() inside an HTML template literal: not exported, call
                  it into a variable before building the HTML
  xml-att-expr    English text inside a t-att-* / t-attf-* expression
  py-exception    Odoo exception raised with a bare string (no _())
  py-format-in-t  _() around an f-string or a %-formatted string

It is a heuristic: review every hit, some are technical strings. Exit code 1
when something was found.
"""

import re
import sys
from pathlib import Path

SKIP_DIRS = {"node_modules", "lib", "tests", "__pycache__", ".git", "i18n"}

# A "sentence-like" literal: starts with a letter, has a space or ends with
# punctuation, and contains at least one lowercase word of 2+ letters.
SENTENCE = r"[A-Za-z][^\"'`\n]*?(?:\s|[.!?:…])[^\"'`\n]*"

JS_CONTEXTS = [
    # notification.add("..."), dialog titles, labels, placeholders, ...
    re.compile(
        r"(?:notification\.add|alert|confirm|prompt)\(\s*([\"'`])(" + SENTENCE + r")\1"
    ),
    re.compile(
        r"\b(?:title|label|placeholder|message|help|string|text|tooltip|"
        r"confirmLabel|cancelLabel|body|name)\s*:\s*([\"'`])([A-Za-z][^\"'`\n]*)\1"
    ),
    # default names: `name || "Custom area"`
    re.compile(r"\|\|\s*([\"'`])([A-Z][^\"'`\n]*[a-z][^\"'`\n]*)\1"),
    # notification.add(`... ${x}`)
    re.compile(r"notification\.add\(\s*(`)([^`]*\$\{[^`]*)`"),
]
JS_HTML_TEXT = re.compile(r">\s*([A-Z][a-z][^<>${}]{2,})\s*<")
JS_HTML_ATTR = re.compile(r"\b(?:title|aria-label|placeholder|alt)=\"([A-Za-z][^\"$]*)\"")
JS_T_TEMPLATE = re.compile(r"_t\(\s*`[^`]*\$\{")

XML_ATT_EXPR = re.compile(
    r"t-att(?:f)?-(?:title|placeholder|aria-label|alt|label|string|data-tooltip)"
    r"=\"([^\"]*)\""
)
QUOTED_WORDS = re.compile(r"'([A-Za-z][^']*\s[^']*)'")

PY_EXCEPTION = re.compile(
    r"raise\s+(?:UserError|ValidationError|AccessError|RedirectWarning|"
    r"MissingError)\(\s*f?[\"']"
)
PY_FORMAT_IN_T = re.compile(
    r"\b_\(\s*f[\"']|\b_\(\s*[\"'][^\"']*[\"']\s*%|\benv\._\(\s*f[\"']"
)

JS_IGNORE = re.compile(
    r"^\s*(?:import|export\s+\*|//|\*|/\*)|console\.|throw new Error|"
    r"querySelector|classList|\bkey ===|registry\.category|useService\(|"
    r"t-name|static template|_t\("
)


def scan_js(path, hits):
    in_html = False
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if "innerHTML" in line or "insertAdjacentHTML" in line:
            in_html = True
        if in_html:
            if "_t(" in line and "innerHTML" not in line:
                hits.append((path, lineno, "js-t-in-template", line.strip()))
            for m in JS_HTML_TEXT.finditer(line):
                hits.append((path, lineno, "js-html", m.group(1).strip()))
            for m in JS_HTML_ATTR.finditer(line):
                hits.append((path, lineno, "js-html", m.group(0)))
            if line.rstrip().endswith("`;"):
                in_html = False
        if JS_T_TEMPLATE.search(line):
            hits.append((path, lineno, "js-template-lit", line.strip()))
        if JS_IGNORE.search(line):
            continue
        for index, rx in enumerate(JS_CONTEXTS):
            for m in rx.finditer(line):
                text = m.group(2)
                if not re.search(r"[a-z]{2}", text):
                    continue
                # single words only count as labels when capitalized
                # ("All", "Finish"), not technical names ("form", "id")
                is_word = re.fullmatch(r"[\w.\-/]+", text)
                if is_word and not (index == 1 and re.fullmatch(r"[A-Z][a-z]+", text)):
                    continue
                hit = (path, lineno, "js-literal", text)
                if hit not in hits:
                    hits.append(hit)


def scan_xml(path, hits):
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        for m in XML_ATT_EXPR.finditer(line):
            for q in QUOTED_WORDS.finditer(m.group(1)):
                hits.append((path, lineno, "xml-att-expr", q.group(1)))


def scan_py(path, hits):
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if PY_EXCEPTION.search(line):
            hits.append((path, lineno, "py-exception", line.strip()))
        if PY_FORMAT_IN_T.search(line):
            hits.append((path, lineno, "py-format-in-t", line.strip()))


def iter_files(root):
    for path in sorted(root.rglob("*")):
        if not path.is_file() or SKIP_DIRS & set(path.relative_to(root).parts):
            continue
        yield path


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    hits = []
    for arg in argv[1:]:
        root = Path(arg).resolve()
        for path in iter_files(root):
            in_static = "static" in path.relative_to(root).parts
            if path.suffix == ".js" and in_static:
                scan_js(path, hits)
            elif path.suffix == ".xml" and in_static:
                scan_xml(path, hits)
            elif path.suffix == ".py":
                scan_py(path, hits)
    for path, lineno, category, snippet in hits:
        print(f"{path}:{lineno} [{category}] {snippet[:120]}")
    print(f"{len(hits)} finding(s)", file=sys.stderr)
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
