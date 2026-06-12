"""Whole-word, plural-aware keyword matching.

Substring matching is the source of a whole class of categorization bugs:
"tea" inside "steak", "egg" inside "eggplant", "water" inside "watermelon",
"ham" inside "graham". This module matches a keyword only against whole tokens
(handling regular plurals), so those false positives disappear while real
matches like "banana" -> "bananas" and "berry" -> "berries" still work.
"""

from __future__ import annotations

import re

_TOKENS = re.compile(r"[a-z]+")
_PLURALS = ("ies", "es", "s")


def _token_matches(tok: str, term: str) -> bool:
    if tok == term:
        return True
    for suf in _PLURALS:
        if tok.endswith(suf) and len(tok) > len(suf):
            stem = tok[: -len(suf)]
            if stem == term:
                return True
            if suf == "ies" and stem + "y" == term:  # berries -> berry
                return True
    return False


def term_in_text(text: str, term: str) -> bool:
    """True if `term` appears in `text` as a whole word (plural-aware).

    Multi-word or punctuated terms (e.g. "ice cream", "half & half") fall back
    to a plain substring check, since those are specific enough not to collide.
    """
    text = text.lower()
    term = term.lower()
    if " " in term or "&" in term:
        return term in text
    return any(_token_matches(tok, term) for tok in _TOKENS.findall(text))


def any_term_in_text(text: str, terms) -> bool:
    return any(term_in_text(text, t) for t in terms)
