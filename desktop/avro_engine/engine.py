# avro_engine/engine.py
"""Pure-Python implementation of the OmicronLab Avro Phonetic algorithm.

The algorithm:
  1. Load `avrophonetic.json` (the same rules file Avro Keyboard ships).
  2. Pre-sort all patterns by `find` length, longest first — so greedy
     matching prefers "kSh" over "k" + "S" + "h".
  3. For each input character, attempt to match the longest pattern
     starting at that position.
  4. A matched pattern has a default `replace` and zero-or-more `rules`.
     Each rule has a list of `matches` (prefix/suffix conditions on the
     surrounding characters); the first rule whose conditions ALL hold
     wins, and its `replace` is used. If no rule matches, the default
     replacement is used.
  5. Move past the matched pattern's length; repeat.
  6. Characters with no pattern match (numbers, punctuation, unknown
     symbols) are emitted verbatim.

Match scopes:
  - "vowel"        — character is in `layout.vowel` (a e i o u)
  - "consonant"    — in `layout.consonant`
  - "number"       — in `layout.number`
  - "punctuation"  — anything else (or off-end-of-string)
  - "exact"        — exact match against rule's `value` field
  - "!scope"       — negation
Match types:
  - "prefix"       — character immediately BEFORE the matched pattern
  - "suffix"       — character immediately AFTER the matched pattern

Case handling:
  `layout.casesensitive` lists letters whose case is significant
  (e.g. 'O' vs 'o' produce different output). Other letters get
  lower-cased before pattern matching.
"""

from __future__ import annotations

import json
import os
from typing import List, Dict, Set


_DEFAULT_RULES_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "avrophonetic.json",
)


class AvroEngine:
    """Holds compiled rules and exposes a single `parse(text)` method."""

    def __init__(self, rules_path: str = _DEFAULT_RULES_PATH):
        with open(rules_path, encoding="utf-8") as fh:
            data = json.load(fh)
        layout = data["layout"]

        self.case_sensitive: Set[str] = set(layout["casesensitive"])
        self.vowels:         Set[str] = set(layout["vowel"])
        self.consonants:     Set[str] = set(layout["consonant"])
        self.numbers:        Set[str] = set(layout["number"])

        # Sort patterns by `find` length descending — greedy longest match
        self.patterns: List[Dict] = sorted(
            layout["patterns"],
            key=lambda p: -len(p["find"]),
        )

    # ── Public API ────────────────────────────────────────────────

    def parse(self, text: str) -> str:
        """Convert a Latin (Avro phonetic) string to Bengali Unicode."""
        if not text:
            return ""
        normalized = self._fix_case(text)
        out: List[str] = []
        i = 0
        n = len(normalized)
        while i < n:
            matched = False
            for pattern in self.patterns:
                find = pattern["find"]
                flen = len(find)
                if i + flen > n:
                    continue
                if normalized[i:i + flen] != find:
                    continue
                # Pattern matches — pick replacement
                replacement = self._evaluate(pattern, normalized, i, flen)
                out.append(replacement)
                i += flen
                matched = True
                break
            if not matched:
                out.append(normalized[i])
                i += 1
        return "".join(out)

    # ── Internal helpers ──────────────────────────────────────────

    def _fix_case(self, text: str) -> str:
        """Lowercase chars that aren't in the case-sensitive set.
        Case-sensitive chars are kept as-is so 'A' vs 'a' stay distinct."""
        out_chars = []
        for ch in text:
            if ch.lower() in self.case_sensitive:
                out_chars.append(ch)            # preserve original case
            else:
                out_chars.append(ch.lower())    # lowercase normalise
        return "".join(out_chars)

    def _evaluate(self, pattern: Dict, text: str, pos: int, flen: int) -> str:
        rules = pattern.get("rules") or []
        for rule in rules:
            if self._all_matches_satisfied(
                    rule.get("matches", []), text, pos, flen):
                return rule.get("replace", "")
        # No rule matched — use default
        return pattern.get("replace", "")

    def _all_matches_satisfied(self, matches: List[Dict], text: str,
                                pos: int, flen: int) -> bool:
        for m in matches:
            if not self._match_one(m, text, pos, flen):
                return False
        return True

    def _match_one(self, m: Dict, text: str, pos: int, flen: int) -> bool:
        scope = m.get("scope", "")
        type_ = m.get("type", "")
        negate = scope.startswith("!")
        if negate:
            scope = scope[1:]

        # Locate the character to test
        if type_ == "prefix":
            idx = pos - 1
        elif type_ == "suffix":
            idx = pos + flen
        else:
            return False

        # Off-the-end is treated as punctuation (start/end of string)
        if idx < 0 or idx >= len(text):
            char_class = "punctuation"
            actual_char = ""
        else:
            actual_char = text[idx]
            char_class = self._classify(actual_char)

        # Apply scope test
        if scope == "exact":
            value = m.get("value", "")
            ok = (actual_char == value)
        else:
            ok = (char_class == scope)

        if negate:
            ok = not ok
        return ok

    def _classify(self, ch: str) -> str:
        if ch in self.vowels:
            return "vowel"
        if ch in self.consonants:
            return "consonant"
        if ch in self.numbers:
            return "number"
        return "punctuation"


# ── Module-level singleton + convenience function ────────────────

_INSTANCE: AvroEngine = None


def _get_engine() -> AvroEngine:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = AvroEngine()
    return _INSTANCE


def parse(text: str) -> str:
    """Module-level shortcut — same signature as `avro.parse()`."""
    return _get_engine().parse(text)
