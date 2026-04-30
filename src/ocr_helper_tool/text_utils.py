from __future__ import annotations


def normalize_text_for_compare(text: str) -> str:
    if not text:
        return ""
    chars = []
    for ch in text:
        if ("\u4e00" <= ch <= "\u9fff") or ch.isalnum():
            chars.append(ch)
    return "".join(chars).lower()

