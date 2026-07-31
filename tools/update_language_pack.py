#!/usr/bin/env python3
"""Prepare, apply and validate ProcessWire JSON language-pack updates.

The tool is deliberately deterministic: an agent translates only an explicit
JSON task. It does not call any translation provider and never needs a secret.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


CALL_PATTERNS = (
    r"(?:>_)\(\s*(['\"])(.+?)(?<!\\)\1\s*\)",
    r"(?:[\s.=(\\,]__|=>__|^__)\(\s*(['\"])(.+?)(?<!\\)\1\s*(?:,\s*[^)]+)?\)",
    r"(?:[\s.=>(\\,]_x|^_x)\(\s*(['\"])(.+?)(?<!\\)\1\s*,\s*(['\"])(.+?)(?<!\\)\3\s*[^)]*\)",
    r"(?:[\s.=>(\\,]_n|^_n)\(\s*(['\"])(.+?)(?<!\\)\1\s*,\s*(['\"])(.+?)(?<!\\)\3\s*,\s*.+?\)",
)
ARRAY_CALL = re.compile(
    r"((?:->_|\b__|\b_n|\b_x)\(\[\s*)(['\"])(.+?)(?<!\\)\2"
    r"([^\]]*?\])\s*([^)]*\))",
    re.MULTILINE,
)
PROTECTED_TOKEN = re.compile(
    r"https?://[^\s<>()\[\]\"']+|`[^`]+`"
    r"|%(?:\d+\$)?[+#0\- ]*\d*(?:\.\d+)?[bcdeEufFgGosxX]"
    r"|\$[A-Za-z_][A-Za-z0-9_]*|\{[^{}]+\}|<[^>]+>"
)
TEXTDOMAIN_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def textdomain(path: str) -> str:
    return path.replace("/", "--").replace(".", "-").lower()


def phrase_hash(text: str, context: str = "") -> str:
    return hashlib.md5((text + context).encode()).hexdigest()


def unescape(text: str) -> str:
    return (text.replace('\\"', '"').replace("\\'", "'")
            .replace('\\$', '$').replace('\\n', '\n').replace('\\\\', '\\'))


def normalize_array_calls(source: str) -> str:
    """Use the first phrase of ProcessWire's array/fallback translation calls."""
    def replace(match: re.Match[str]) -> str:
        return match.group(1).replace("[", "") + match.group(2) + match.group(3) + match.group(2) + match.group(5)
    return ARRAY_CALL.sub(replace, source)


def phrases(source: str) -> list[tuple[str, str]]:
    """Mirror ProcessWire LanguageParser's literal-call handling and keys."""
    found: list[tuple[str, str]] = []
    source = normalize_array_calls(source)
    for kind, pattern in enumerate(CALL_PATTERNS):
        for match in re.finditer(pattern, source, re.MULTILINE):
            context = unescape(match.group(4)) if kind == 2 else ""
            found.append((unescape(match.group(2)), context))
            if kind == 3:  # _n(): singular and plural are separate keys
                found.append((unescape(match.group(4)), ""))
    return found


def load_pack(pack: Path) -> tuple[dict[str, tuple[Path, dict[str, Any]]], dict[str, str]]:
    files: dict[str, tuple[Path, dict[str, Any]]] = {}
    known: dict[str, str] = {}
    for file in pack.glob("*.json"):
        data = json.loads(file.read_text())
        required = {"file", "textdomain", "translations"}
        if not required.issubset(data):
            continue  # Translation tasks/reports may be kept beside the pack temporarily.
        if isinstance(data["translations"], list):
            if data["translations"]:
                raise ValueError(f"Invalid language file: {file}")
            data["translations"] = {}
        elif not isinstance(data["translations"], dict):
            raise ValueError(f"Invalid language file: {file}")
        domain = data["textdomain"]
        files[domain] = (file, data)
        for key, value in data["translations"].items():
            if isinstance(value, dict) and isinstance(value.get("text"), str) and value["text"]:
                known.setdefault(key, value["text"])
    return files, known


def scan_core(core: Path) -> tuple[dict[str, dict[str, tuple[str, str]]], dict[str, str]]:
    wire = core / "wire"
    if not wire.is_dir():
        raise ValueError(f"Core directory has no wire/ folder: {core}")
    entries: dict[str, dict[str, tuple[str, str]]] = defaultdict(dict)
    paths: dict[str, str] = {}
    for source_file in wire.rglob("*.php"):
        relative = source_file.relative_to(core).as_posix()
        domain = textdomain(relative)
        extracted = phrases(source_file.read_text(errors="replace"))
        if extracted:
            paths[domain] = relative
        for phrase, context in extracted:
            entries[domain][phrase_hash(phrase, context)] = (phrase, context)
    return entries, paths


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=True, indent=4).replace("/", r"\/"))


def command_prepare(args: argparse.Namespace) -> int:
    pack = Path(args.pack).resolve()
    core = Path(args.core).resolve()
    files, known = load_pack(pack)
    core_entries, paths = scan_core(core)
    updates: list[dict[str, Any]] = []
    for domain, entries in sorted(core_entries.items()):
        current = files.get(domain, (None, {"translations": {}}))[1]["translations"]
        for key, (source, context) in sorted(entries.items()):
            if key not in current:
                updates.append({
                    "textdomain": domain,
                    "file": paths[domain],
                    "hash": key,
                    "source": source,
                    "context": context,
                    "translation": known.get(key),
                })
    task = {
        "format": 1,
        "core_version": args.version,
        "instructions": "Translate only entries with null translation. Preserve placeholders, code, HTML, URLs and product names.",
        "entries": updates,
    }
    output = Path(args.output)
    output.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n")
    needs_translation = sum(item["translation"] is None for item in updates)
    print(f"Prepared {len(updates)} entries ({needs_translation} need translation): {output}")
    return 0


def protected_tokens(text: str) -> list[str]:
    return sorted(PROTECTED_TOKEN.findall(text))


def validate_task_entry(item: Any) -> tuple[str, str, str, str, str, str | None]:
    if not isinstance(item, dict):
        raise ValueError("Task entry must be an object")
    required = ("textdomain", "file", "hash", "source", "context", "translation")
    if any(key not in item for key in required):
        raise ValueError("Task entry has missing required fields")
    domain, file, key, source, context, translation = (item[key] for key in required)
    if not all(isinstance(value, str) for value in (domain, file, key, source, context)):
        raise ValueError("Task entry has invalid string fields")
    relative = Path(file)
    if (not TEXTDOMAIN_RE.fullmatch(domain) or relative.is_absolute() or ".." in relative.parts
            or relative.as_posix() != file or not file.startswith("wire/") or not file.endswith(".php")
            or textdomain(file) != domain or phrase_hash(source, context) != key):
        raise ValueError(f"Invalid task entry: {domain}:{key}")
    if translation is not None and not isinstance(translation, str):
        raise ValueError(f"Invalid prefilled translation for {domain}:{key}")
    return domain, file, key, source, context, translation


def command_apply(args: argparse.Namespace) -> int:
    pack = Path(args.pack).resolve()
    task = json.loads(Path(args.task).read_text())
    answers = json.loads(Path(args.translations).read_text())
    translations = answers.get("translations", answers)
    if not isinstance(translations, dict):
        raise ValueError("Translations must be an object keyed by phrase hash")
    if not isinstance(task, dict) or task.get("format") != 1 or not isinstance(task.get("entries"), list):
        raise ValueError("Invalid translation task")
    files, _ = load_pack(pack)
    touched: set[str] = set()
    added = 0
    required_hashes: set[str] = set()
    for item in task["entries"]:
        domain, source_file, key, source, _context, prefilled = validate_task_entry(item)
        if prefilled is None:
            required_hashes.add(key)
        if domain not in files:
            file = pack / f"{domain}.json"
            data = {"file": source_file, "textdomain": domain, "translations": {}}
            files[domain] = (file, data)
        file, data = files[domain]
        if key in data["translations"]:
            continue
        translated = prefilled
        if translated is None:
            translated = translations.get(key)
        if not isinstance(translated, str) or not translated.strip():
            raise ValueError(f"Missing translation for {domain}:{key}")
        if protected_tokens(source) != protected_tokens(translated):
            raise ValueError(f"Protected token mismatch for {domain}:{key}")
        data["translations"][key] = {"text": translated}
        touched.add(domain)
        added += 1
    unexpected = set(translations) - required_hashes
    if unexpected:
        raise ValueError(f"Translation file contains unexpected hash(es): {', '.join(sorted(unexpected)[:3])}")
    for domain in touched:
        file, data = files[domain]
        write_json(file, data)
    if args.version:
        (pack / "PROCESSWIRE_STABLE_VERSION").write_text(args.version + "\n")
    print(f"Applied {added} entries in {len(touched)} language files")
    return 0


def command_validate(args: argparse.Namespace) -> int:
    pack = Path(args.pack).resolve()
    core = Path(args.core).resolve()
    files, _ = load_pack(pack)
    core_entries, _ = scan_core(core)
    missing: list[str] = []
    blanks: list[str] = []
    for domain, entries in core_entries.items():
        if domain not in files:
            missing.extend(f"{domain}:{key} {source!r}" for key, (source, _context) in entries.items())
            continue
        _, data = files[domain]
        for key, (source, _context) in entries.items():
            value = data["translations"].get(key)
            if value is None:
                missing.append(f"{domain}:{key} {source!r}")
            elif not isinstance(value, dict) or not value.get("text"):
                blanks.append(f"{domain}:{key} {source!r}")
    if missing or blanks:
        for item in missing + blanks:
            print(item, file=sys.stderr)
        raise ValueError(f"Validation failed: {len(missing)} missing, {len(blanks)} blank")
    print(f"Validated {len(files)} JSON language files against {len(core_entries)} core textdomains")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("prepare", "validate"):
        command = commands.add_parser(name)
        command.add_argument("--pack", default=".")
        command.add_argument("--core", required=True)
        if name == "prepare":
            command.add_argument("--version", required=True)
            command.add_argument("--output", default="translation-task.json")
    apply = commands.add_parser("apply")
    apply.add_argument("--pack", default=".")
    apply.add_argument("--task", required=True)
    apply.add_argument("--translations", required=True)
    apply.add_argument("--version")
    args = parser.parse_args()
    return {"prepare": command_prepare, "apply": command_apply, "validate": command_validate}[args.command](args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
