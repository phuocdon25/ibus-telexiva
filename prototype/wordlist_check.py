#!/usr/bin/env python3
"""Kiểm tra bộ Telex với một danh sách từ tiếng Việt.

Với mỗi âm tiết trong danh sách, sinh nhiều cách gõ Telex khác nhau (mỗi người gõ một kiểu),
chạy qua telex.finalize và so với âm tiết gốc.

Chạy:
    python3 prototype/wordlist_check.py <wordlist.txt> [--show N]

Danh sách từ không nằm trong repo (ví dụ Viet74K.txt của duyet/vietnamese-wordlist).
"""

from __future__ import annotations

import sys
import unicodedata
from collections import Counter, defaultdict

from telex import FINALS, NEED_FINAL, NUCLEI, OPEN_ONLY, STOP_FINALS, TONED, _split, _tone_index, finalize

# ký tự có dấu mũ/móc -> (chữ gốc, phím tạo dấu)
MODIFIED = {"â": ("a", "a"), "ê": ("e", "e"), "ô": ("o", "o"),
            "ă": ("a", "w"), "ơ": ("o", "w"), "ư": ("u", "w"), "đ": ("d", "d")}
TONE_KEY = {1: "s", 2: "f", 3: "r", 4: "x", 5: "j"}
VOWEL_BASES = set("aăâeêioôơuưy")


def decompose(syl: str):
    """'tiếng' -> (['t','i','ê','n','g'], tone=1). None nếu có ký tự lạ."""
    chars, tone = [], 0
    for c in syl:
        for base, forms in TONED.items():
            if c in forms:
                t = forms.index(c)
                if t:
                    if tone:
                        return None
                    tone = t
                chars.append(base)
                break
        else:
            if c == "đ" or ("a" <= c <= "z"):
                chars.append(c)
            else:
                return None
    return chars, tone


def is_standard_syllable(syl, chars, tone) -> bool:
    """Chỉ giữ âm tiết tiếng Việt chuẩn: bỏ từ mượn viết liền (alô, amiđan), lỗi chính tả
    trong danh sách (ngươí, trưởnc), từ tiếng Anh (as) và vần "oo" mơ hồ (boóc ~ bốc)."""
    parts = _split("".join(chars))
    if parts is None:
        return False
    initial, nucleus, final = parts
    if nucleus not in NUCLEI or nucleus == "oo" or (final and final not in FINALS):
        return False
    if final and nucleus in OPEN_ONLY:
        return False
    if not final and nucleus in NEED_FINAL:
        return False   # ví dụ "ngườ" (lỗi trong danh sách)
    if final in STOP_FINALS and tone in (2, 3, 4):
        return False
    if not tone:
        return True
    # Dấu thanh phải nằm đúng vị trí theo kiểu cũ hoặc kiểu mới.
    pos = next(i for i, c in enumerate(syl) if c not in "".join(chars)[i:i + 1])
    allowed = {len(initial) + _tone_index(nucleus, bool(final), ns) for ns in (False, True)}
    return pos in allowed


def plain(chars):
    return "".join(MODIFIED[c][0] if c in MODIFIED else c for c in chars)


def last_vowel_pos(chars):
    return max(i for i, c in enumerate(chars) if c in VOWEL_BASES)


def variants(chars, tone):
    """Sinh các chuỗi phím Telex khác nhau cho cùng một âm tiết."""
    tk = TONE_KEY.get(tone, "")
    out = {}

    def immediate(uwow=False):
        keys = []
        i = 0
        while i < len(chars):
            c = chars[i]
            if c == "ư" and i + 1 < len(chars) and chars[i + 1] == "ơ":
                keys += ["u", "w", "o", "w"] if uwow else ["u", "o", "w"]
                i += 2
                continue
            if c in MODIFIED:
                base, mod = MODIFIED[c]
                keys += [base, mod]
            else:
                keys.append(c)
            i += 1
        return keys

    std = immediate()
    out["chuẩn (dấu cuối từ)"] = "".join(std) + tk
    if any(c in ("ư",) for c in chars) and "ươ" in "".join(chars):
        out["uwow"] = "".join(immediate(uwow=True)) + tk

    if tk:
        # dấu thanh ngay sau nguyên âm cuối cùng của vần
        keys = immediate()
        # vị trí sau phím cuối cùng thuộc vần trong chuỗi phím
        consonant_tail = 0
        for c in reversed(chars):
            if c in VOWEL_BASES:
                break
            consonant_tail += 1
        tail = "".join(chars[len(chars) - consonant_tail:])
        if consonant_tail and "".join(keys).endswith(tail):
            k = "".join(keys)
            out["dấu sau nguyên âm"] = k[: len(k) - len(tail)] + tk + tail

    # dấu mũ/móc/đ gõ ở cuối từ
    mods = []
    if "ươ" in "".join(chars):
        mods.append("w")
    for c in chars:
        if c in MODIFIED and not (c in "ươ" and "ươ" in "".join(chars)):
            mods.append(MODIFIED[c][1])
    if mods:
        out["mũ/móc gõ cuối"] = plain(chars) + "".join(dict.fromkeys(mods)) + tk
        out["mũ/móc sau dấu thanh"] = plain(chars) + tk + "".join(dict.fromkeys(mods))
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    show = 15
    if "--show" in sys.argv:
        show = int(sys.argv[sys.argv.index("--show") + 1])

    syllables = set()
    with open(sys.argv[1], encoding="utf-8") as f:
        for line in f:
            for w in line.replace("-", " ").split():
                w = unicodedata.normalize("NFC", w.strip().lower())
                if w:
                    syllables.add(w)

    tested = 0
    fails = defaultdict(list)
    style_only = 0
    skipped = 0
    for syl in sorted(syllables):
        d = decompose(syl)
        if d is None or not any(c in VOWEL_BASES for c in d[0]):
            skipped += 1
            continue
        chars, tone = d
        if not is_standard_syllable(syl, chars, tone):
            skipped += 1
            continue
        for label, keys in variants(chars, tone).items():
            for cased_keys, want in ((keys, syl), (keys[0].upper() + keys[1:], syl[0].upper() + syl[1:])):
                tested += 1
                got = finalize(cased_keys)
                if got == want:
                    continue
                if finalize(cased_keys, new_style=True) == want:
                    style_only += 1   # danh sách dùng kiểu đặt dấu mới (hoà), không phải lỗi
                    continue
                fails[label].append((cased_keys, want, got))

    total_fail = sum(len(v) for v in fails.values())
    print(f"Âm tiết: {len(syllables)} (bỏ qua {skipped}: từ mượn, lỗi chính tả trong danh sách, từ tiếng Anh)")
    print(f"Số ca gõ đã kiểm tra: {tested}")
    print(f"Đúng: {tested - total_fail - style_only}  |  Chỉ khác kiểu đặt dấu (hoà/hòa): {style_only}"
          f"  |  SAI: {total_fail}")
    for label, items in fails.items():
        print(f"\n== {label}: {len(items)} ca sai")
        by_want = Counter()
        for keys, want, got in items[:show]:
            print(f"   {keys:14} -> {got:14} (đúng: {want})")
            by_want[want] += 1
    sys.exit(1 if total_fail else 0)


if __name__ == "__main__":
    main()
