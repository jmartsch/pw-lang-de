#!/usr/bin/env python3
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).parents[1] / "tools" / "update_language_pack.py"


def md5(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


class LanguagePackToolTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.root = root
        self.pack = root / "pack"
        self.core = root / "core"
        self.pack.mkdir()
        source = self.core / "wire" / "core" / "New.php"
        source.parent.mkdir(parents=True)
        source.write_text(
            "<?php\n"
            "__('Hello');\n"
            "__('Delete %s %s at https://example.com/a `code`');\n"
            "_x('Open', 'verb');\n"
            "_x('Open', 'adjective');\n"
            "_n('one item', 'many items', $count);\n"
            "__(['Modern', 'Legacy']);\n"
            "__('Escaped \\\"quote\\\"');\n"
        )
        old = {
            "file": "wire/core/Old.php",
            "textdomain": "wire--core--old-php",
            "translations": {md5("Hello"): {"text": "Hallo"}},
        }
        (self.pack / "wire--core--old-php.json").write_text(json.dumps(old))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_tool(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["python3", str(TOOL), *args], text=True, capture_output=True, check=check)

    def prepare(self) -> tuple[Path, list[dict]]:
        task = self.pack / "task.json"
        self.run_tool("prepare", "--pack", str(self.pack), "--core", str(self.core), "--version", "3.0.999", "--output", str(task))
        return task, json.loads(task.read_text())["entries"]

    def test_prepare_apply_and_validate_all_processwire_call_forms(self) -> None:
        task, entries = self.prepare()
        self.assertEqual(8, len(entries))
        hello = next(item for item in entries if item["source"] == "Hello")
        self.assertEqual("Hallo", hello["translation"])
        self.assertEqual(md5("Openverb"), next(item for item in entries if item["context"] == "verb")["hash"])
        self.assertEqual(md5("Openadjective"), next(item for item in entries if item["context"] == "adjective")["hash"])
        self.assertIn("Modern", [item["source"] for item in entries])
        self.assertNotIn("Legacy", [item["source"] for item in entries])
        self.assertIn('Escaped "quote"', [item["source"] for item in entries])
        german = {
            "Delete %s %s at https://example.com/a `code`": "Löschen %s %s unter https://example.com/a `code`",
            "Open": "Öffnen",
            "one item": "ein Element",
            "many items": "mehrere Elemente",
            "Modern": "Modern",
            'Escaped "quote"': 'Maskiertes "Zitat"',
        }
        answer = self.pack / "translations.json"
        answer.write_text(json.dumps({"translations": {
            item["hash"]: german[item["source"]] for item in entries if item["translation"] is None
        }}))
        self.run_tool("apply", "--pack", str(self.pack), "--task", str(task), "--translations", str(answer), "--version", "3.0.999")
        self.run_tool("validate", "--pack", str(self.pack), "--core", str(self.core))
        language_file = json.loads((self.pack / "wire--core--new-php.json").read_text())
        self.assertEqual("Hallo", language_file["translations"][hello["hash"]]["text"])
        self.assertEqual("3.0.999\n", (self.pack / "PROCESSWIRE_STABLE_VERSION").read_text())

    def test_apply_rejects_damaged_repeated_placeholder_url_or_code_span(self) -> None:
        task, entries = self.prepare()
        protected = next(item for item in entries if item["source"].startswith("Delete"))
        answer = self.pack / "translations.json"
        answers = {item["hash"]: "Übersetzung" for item in entries if item["translation"] is None}
        answers[protected["hash"]] = "Löschen %s unter https://example.com/a"
        answer.write_text(json.dumps(answers))
        result = self.run_tool("apply", "--pack", str(self.pack), "--task", str(task), "--translations", str(answer), check=False)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("Protected token mismatch", result.stderr)

    def test_apply_rejects_path_traversal_in_task(self) -> None:
        task, entries = self.prepare()
        entry = next(item for item in entries if item["translation"] is None)
        entry["textdomain"] = "../../outside"
        malicious = self.pack / "malicious-task.json"
        malicious.write_text(json.dumps({"format": 1, "entries": [entry]}))
        answer = self.pack / "translations.json"
        answer.write_text(json.dumps({entry["hash"]: "Übersetzung"}))
        result = self.run_tool("apply", "--pack", str(self.pack), "--task", str(malicious), "--translations", str(answer), check=False)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("Invalid task entry", result.stderr)
        self.assertFalse((self.root / "outside.json").exists())


if __name__ == "__main__":
    unittest.main()
