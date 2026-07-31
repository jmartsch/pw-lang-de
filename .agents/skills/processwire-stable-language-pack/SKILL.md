---
name: processwire-stable-language-pack
description: Use when updating this ProcessWire language pack to a new stable core with the maintainer's own Codex or GPT.
version: 1.0.0
author: pw-lang-de contributors
license: MIT
metadata:
  hermes:
    tags: [processwire, i18n, translation, codex, gpt, release]
    related_skills: []
---

# ProcessWire stable language-pack update

## Overview

This repository contains the formal German (`de_DE`) ProcessWire language pack. The deterministic tool under `tools/` finds new literal ProcessWire translation calls and verifies the pack. The current agent performs the German translation using its own authenticated Codex/GPT session; no translation API, key or provider is embedded in this repository.

## When to use

- A new ProcessWire stable version is announced.
- The `Check ProcessWire stable` workflow opens an update issue.
- A maintainer asks to refresh this language pack against a supplied stable checkout.

Do not use this workflow for ProcessWire development snapshots or third-party module translations unless they are deliberately part of this pack.

## Update workflow

1. **Start clean and identify the official stable version.**

   ```bash
   git status --short
   git clone --depth 1 --branch 3.0.256 https://github.com/processwire/processwire.git /tmp/processwire-3.0.256
   ```

   Completion: the language-pack worktree is clean and `git -C /tmp/processwire-3.0.256 describe --tags --exact-match` returns the requested stable tag.

2. **Create a new branch and generate the translation task.**

   ```bash
   git switch -c chore/processwire-3.0.256-language-pack
   python3 tools/update_language_pack.py prepare \
     --core /tmp/processwire-3.0.256 \
     --version 3.0.256 \
     --output /tmp/processwire-3.0.256-translation-task.json
   ```

   Completion: inspect the task. Entries with a non-null `translation` are safe reuses of an existing German translation. Only null entries need translation.

3. **Translate with the active agent, never an embedded provider.**

   Translate only each null `translation` in the task, using formal German ("Sie"). Produce an answer JSON object shaped as:

   ```json
   {
     "translations": {
       "md5-phrase-hash": "Deutsche Übersetzung"
     }
   }
   ```

   Preserve every printf placeholder (`%s`, `%1$d`), PHP/JavaScript variable, URL, HTML tag, code span and product name exactly. Do not change source text or keys. The agent may use its own Codex/GPT authentication, but this repository must never receive its credentials.

4. **Apply and validate.**

   ```bash
   python3 tools/update_language_pack.py apply \
     --task /tmp/processwire-3.0.256-translation-task.json \
     --translations /tmp/processwire-3.0.256-translations.json \
     --version 3.0.256
   python3 tools/update_language_pack.py validate --core /tmp/processwire-3.0.256
   python3 -m unittest discover -s tests -v
   git diff --check
   ```

   Completion: all commands succeed. `PROCESSWIRE_STABLE_VERSION` contains the new stable version.

5. **Perform language QA and publish a narrow PR.**

   Review all new translations for formal address, ProcessWire terminology and correct German. Stage only JSON language files plus `PROCESSWIRE_STABLE_VERSION`; do not commit `/tmp` task files. Build a ZIP from the index and run `unzip -t` before opening the pull request.

## Safety rules

- Never overwrite an existing translation merely because an agent proposes a different wording.
- Never use a hosted translation API from this repository or GitHub Actions.
- Do not claim support for a stable version until every newly detected phrase is non-empty and the validator passes.
- Keep the stable-check workflow notification-only. It must not write translations or create release commits.

## Verification checklist

- [ ] Core checkout is the official requested stable tag.
- [ ] Translation task has been generated from that checkout.
- [ ] Null task entries are all translated with formal German.
- [ ] Protected tokens match source and translation.
- [ ] `validate`, unit tests and `git diff --check` pass.
- [ ] ZIP integrity test passes.
- [ ] PR contains only the intended language files and version marker.
