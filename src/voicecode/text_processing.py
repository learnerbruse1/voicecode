"""Transcript post-processing modes."""

from __future__ import annotations

import re


def post_process_text(text: str, mode: str) -> str:
    processed = " ".join(text.split()) if mode != "plain" else text.strip()
    if mode == "coding":
        replacements = [
            (r"\bnew line\b", "\n"),
            (r"\btab\b", "    "),
            (r"\bopen parenthesis\b", "("),
            (r"\bclose parenthesis\b", ")"),
            (r"\bopen bracket\b", "["),
            (r"\bclose bracket\b", "]"),
            (r"\bopen brace\b", "{"),
            (r"\bclose brace\b", "}"),
            (r"\bequals\b", "="),
            (r"\bcomma\b", ","),
            (r"\bsemicolon\b", ";"),
            (r"\bcolon\b", ":"),
            (r"\bdot\b", "."),
            (r"\barrow\b", "=>"),
        ]
        for pattern, replacement in replacements:
            processed = re.sub(pattern, replacement, processed, flags=re.IGNORECASE)
    elif mode == "markdown":
        processed = re.sub(r"^heading one\s+", "# ", processed, flags=re.IGNORECASE)
        processed = re.sub(r"^heading two\s+", "## ", processed, flags=re.IGNORECASE)
        processed = re.sub(r"^bullet point\s+", "- ", processed, flags=re.IGNORECASE)
    elif mode == "prompt":
        processed = processed.strip()
        if processed and processed[-1] not in ".!?。！？":
            processed += "."
    return processed.strip()
