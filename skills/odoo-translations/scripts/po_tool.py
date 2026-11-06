#!/usr/bin/env python3
"""Merge an Odoo POT into a .po, list what is untranslated, fill translations.

The .po entries themselves always come from Odoo's export: this tool never
invents an entry, it only merges the exported POT and writes msgstr values,
checking that each translation keeps the "system syntax" of its msgid
(placeholders, markup, surrounding whitespace).

    po_tool.py merge <lang.po> <module.pot> [--lang de]
        Add the new terms of the POT to the .po (created from the POT if
        missing), keep existing translations, drop terms no longer exported.
        Written like Odoo writes .po files (polib, 78 columns), so the diff
        only shows real changes.

    po_tool.py todo <lang.po> [--include-readme] [--include-llm] > todo.json
        Untranslated (or fuzzy) terms as {msgid: ""} plus a "_context" list
        with where each term comes from. Fill in the values. The module
        description and texts for the language model are left out by default.

    po_tool.py fill <lang.po> <todo.json> [--overwrite]
        Write the translations of todo.json. Only empty or fuzzy msgstr are
        filled unless --overwrite. Translations whose syntax differs from the
        msgid are refused and reported; nothing is written if any is refused.

Requires polib (`pip install polib`; Odoo itself depends on it).
"""

import argparse
import json
import logging
import re
import sys
from collections import Counter
from pathlib import Path

try:
    import polib
except ImportError:  # pragma: no cover - environment dependent
    sys.exit("polib is missing: pip install polib")

_logger = logging.getLogger("po_tool")

PLURAL_FORMS = {
    "de": "nplurals=2; plural=(n != 1);",
    "en": "nplurals=2; plural=(n != 1);",
    "es": "nplurals=2; plural=(n != 1);",
    "it": "nplurals=2; plural=(n != 1);",
    "nl": "nplurals=2; plural=(n != 1);",
    "fr": "nplurals=2; plural=(n > 1);",
}

# Placeholders Odoo resolves after the lookup: Python %-format, str.format,
# JS sprintf of _t(), and ${...} that should never be inside a term.
PLACEHOLDER_RE = re.compile(
    r"%\([A-Za-z_][A-Za-z0-9_]*\)[sdrfi]"  # %(name)s
    r"|%[sdrfi]"  # %s
    r"|%%"  # literal percent
    r"|\{[A-Za-z_0-9]*\}"  # {name} / {0} / {}
    r"|\$\{[^}]*\}"  # ${expr}
)
# Markup of view terms (<span class="...">, <br/>, t-* attributes, ...).
TAG_RE = re.compile(r"<[^<>]+>")
# Module descriptions exported from README/index.html: rarely worth it.
README_HINT_RE = re.compile(r"^\s*(\.\. |=+\n|<section|<div class=\"document\")")
# Texts for the language model (AI tool descriptions, prompts): translating
# them changes what the agent does, so they are left out unless asked for.
LLM_FIELD_RE = re.compile(r"ai_tool_description|prompt|system_message|instruction")


def _load(path, wrapwidth=78):
    return polib.pofile(str(path), wrapwidth=wrapwidth)


def _key(entry):
    return (entry.msgctxt or "", entry.msgid)


def _edges(text):
    """Leading and trailing whitespace, which must survive translation."""
    match = re.match(r"^(\s*).*?(\s*)$", text, re.DOTALL)
    return match.group(1), match.group(2)


def check_syntax(msgid, msgstr):
    """Problems of a translation compared to its source, empty if fine."""
    problems = []
    source_placeholders = PLACEHOLDER_RE.findall(msgid)
    target_placeholders = PLACEHOLDER_RE.findall(msgstr)
    if Counter(source_placeholders) != Counter(target_placeholders):
        problems.append(
            f"placeholders differ: {sorted(source_placeholders)} "
            f"vs {sorted(target_placeholders)}"
        )
    if Counter(TAG_RE.findall(msgid)) != Counter(TAG_RE.findall(msgstr)):
        problems.append("markup differs (tags and attributes must stay identical)")
    if _edges(msgid) != _edges(msgstr):
        problems.append("leading/trailing whitespace or newlines differ")
    if msgid.count("\n") and not msgstr.count("\n"):
        problems.append("line breaks of a multi-line term were lost")
    return problems


def cmd_merge(args):
    po_path = Path(args.po)
    lang = args.lang or po_path.stem
    pot = _load(args.pot)
    if po_path.exists():
        po = _load(po_path)
    else:
        po = polib.POFile(wrapwidth=78)
        po.header = pot.header
        po.metadata = dict(pot.metadata)
        po.metadata["Plural-Forms"] = PLURAL_FORMS.get(
            lang.split("_")[0], po.metadata.get("Plural-Forms", "")
        )
    existing = {_key(entry): entry for entry in po if not entry.obsolete}
    merged = polib.POFile(wrapwidth=78)
    merged.header = po.header
    merged.metadata = dict(po.metadata)
    if not merged.metadata.get("Language"):
        merged.metadata["Language"] = lang
    merged.metadata["POT-Creation-Date"] = pot.metadata.get(
        "POT-Creation-Date", merged.metadata.get("POT-Creation-Date", "")
    )
    added = kept = 0
    for source in pot:
        entry = polib.POEntry(
            msgid=source.msgid,
            msgctxt=source.msgctxt,
            comment=source.comment,
            tcomment=source.tcomment,
            occurrences=source.occurrences,
            flags=list(source.flags),
        )
        old = existing.get(_key(source))
        if old is not None:
            entry.msgstr = old.msgstr
            if "fuzzy" in old.flags and "fuzzy" not in entry.flags:
                entry.flags.append("fuzzy")
            kept += 1
        else:
            entry.msgstr = ""
            added += 1
        merged.append(entry)
    dropped = len(existing) - kept
    merged.save(str(po_path))
    _logger.info(
        "%(po)s: %(kept)s kept, %(added)s new, %(dropped)s no longer exported",
        {"po": po_path, "kept": kept, "added": added, "dropped": dropped},
    )


def _is_readme(entry):
    return bool(README_HINT_RE.search(entry.msgid)) or any(
        "ir.module.module" in (occurrence[0] or "") for occurrence in entry.occurrences
    )


def _is_llm_text(entry):
    return any(
        LLM_FIELD_RE.search(occurrence[0] or "") for occurrence in entry.occurrences
    )


def cmd_todo(args):
    po = _load(args.po)
    todo = {}
    context = []
    for entry in po:
        if entry.obsolete or not entry.msgid:
            continue
        if entry.msgstr and "fuzzy" not in entry.flags:
            continue
        if not args.include_readme and _is_readme(entry):
            continue
        if not args.include_llm and _is_llm_text(entry):
            continue
        todo[entry.msgid] = ""
        context.append(
            {
                "msgid": entry.msgid,
                "msgctxt": entry.msgctxt,
                "where": [occurrence[0] for occurrence in entry.occurrences][:3],
                "placeholders": PLACEHOLDER_RE.findall(entry.msgid),
                "tags": TAG_RE.findall(entry.msgid),
            }
        )
    json.dump(
        {"translations": todo, "_context": context},
        sys.stdout,
        ensure_ascii=False,
        indent=2,
    )
    sys.stdout.write("\n")


def cmd_fill(args):
    po_path = Path(args.po)
    po = _load(po_path)
    data = json.loads(Path(args.json).read_text(encoding="utf-8"))
    translations = data.get("translations", data)
    by_msgid = {}
    for entry in po:
        if not entry.obsolete and entry.msgid:
            by_msgid.setdefault(entry.msgid, []).append(entry)
    refused, unknown, filled, skipped = [], [], 0, 0
    for msgid, msgstr in translations.items():
        if msgid.startswith("_") or not msgstr:
            continue
        entries = by_msgid.get(msgid)
        if not entries:
            unknown.append(msgid)
            continue
        problems = check_syntax(msgid, msgstr)
        if problems:
            refused.append((msgid, problems))
            continue
        for entry in entries:
            if entry.msgstr and "fuzzy" not in entry.flags and not args.overwrite:
                skipped += 1
                continue
            entry.msgstr = msgstr
            if "fuzzy" in entry.flags:
                entry.flags.remove("fuzzy")
            filled += 1
    for msgid in unknown:
        _logger.error("not in the .po (export it from Odoo first): %r", msgid)
    for msgid, problems in refused:
        _logger.error("refused %r: %s", msgid, "; ".join(problems))
    if refused or unknown:
        _logger.error("nothing written")
        return 1
    po.save(str(po_path))
    _logger.info(
        "%(po)s: %(filled)s filled, %(skipped)s already translated (kept)",
        {"po": po_path, "filled": filled, "skipped": skipped},
    )
    return 0


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    merge = sub.add_parser("merge", help="merge an exported POT into a .po")
    merge.add_argument("po")
    merge.add_argument("pot")
    merge.add_argument(
        "--lang", help="language code, default: the .po file name (de.po -> de)"
    )
    merge.set_defaults(func=cmd_merge)

    todo = sub.add_parser("todo", help="list untranslated terms as JSON")
    todo.add_argument("po")
    todo.add_argument(
        "--include-readme",
        action="store_true",
        help="also list the module description (README) terms",
    )
    todo.add_argument(
        "--include-llm",
        action="store_true",
        help="also list texts for the language model (AI tool descriptions, "
        "prompts); translating them changes the agent's behaviour",
    )
    todo.set_defaults(func=cmd_todo)

    fill = sub.add_parser("fill", help="write translations from a JSON file")
    fill.add_argument("po")
    fill.add_argument("json")
    fill.add_argument("--overwrite", action="store_true")
    fill.set_defaults(func=cmd_fill)

    args = parser.parse_args()
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
