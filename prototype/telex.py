"""Telex tối giản cho prototype Phase 0.

Hàm thuần, không phụ thuộc IBus, để test được bằng unittest.

- transform(keys)  : chữ hiển thị trong lúc đang gõ (kiểm tra chính tả "lỏng":
                     chuỗi chỉ cần có thể trở thành âm tiết hợp lệ).
- finalize(keys)   : chữ cuối cùng khi kết thúc từ (kiểm tra chặt; sai chính tả
                     thì trả lại nguyên chuỗi phím gốc, ví dụ "text" -> "text").

Không nhằm đầy đủ như FR-001; chỉ đủ để kiểm chứng commit strategy.
"""

from __future__ import annotations

TONE_KEYS = {"s": 1, "f": 2, "r": 3, "x": 4, "j": 5}

# Mỗi nguyên âm -> 6 dạng: không dấu, sắc, huyền, hỏi, ngã, nặng.
TONED = {
    "a": "aáàảãạ", "ă": "ăắằẳẵặ", "â": "âấầẩẫậ",
    "e": "eéèẻẽẹ", "ê": "êếềểễệ",
    "i": "iíìỉĩị",
    "o": "oóòỏõọ", "ô": "ôốồổỗộ", "ơ": "ơớờởỡợ",
    "u": "uúùủũụ", "ư": "ưứừửữự",
    "y": "yýỳỷỹỵ",
}
VOWELS = set(TONED)
BASE = {"ă": "a", "â": "a", "ê": "e", "ô": "o", "ơ": "o", "ư": "u"}
CIRCUMFLEX = {"a": "â", "e": "ê", "o": "ô"}
HORN_DIACRITICS = {"â", "ă", "ê", "ô", "ơ", "ư"}

INITIALS = sorted(
    ["ngh", "ng", "nh", "ch", "gh", "gi", "kh", "ph", "qu", "th", "tr",
     "b", "c", "d", "đ", "g", "h", "k", "l", "m", "n", "p", "r", "s", "t", "v", "x"],
    key=len, reverse=True,
)
FINALS = {"c", "ch", "m", "n", "ng", "nh", "p", "t"}
FINAL_PREFIXES = {f[:i] for f in FINALS for i in range(len(f) + 1)}
STOP_FINALS = {"c", "ch", "p", "t"}

NUCLEI = {
    "a", "ă", "â", "e", "ê", "i", "o", "ô", "ơ", "u", "ư", "y",
    "ai", "ao", "au", "ay", "âu", "ây", "eo", "êu", "ia", "iê", "iu",
    "oa", "oă", "oe", "oi", "ôi", "ơi", "oo", "ua", "uâ", "uê", "ui",
    "uô", "uơ", "uy", "ưa", "ưi", "ưu", "ươ", "yê",
    "iêu", "yêu", "oai", "oay", "oeo", "uây", "uôi", "uya", "uyê", "uyu",
    "ươi", "ươu",
}
# Vần mở: không được có phụ âm cuối.
OPEN_ONLY = {
    "ai", "ao", "au", "ay", "âu", "ây", "eo", "êu", "ia", "iu", "oi", "ôi",
    "ơi", "ua", "ui", "ưa", "ưi", "ưu", "iêu", "yêu", "oai", "oay", "oeo",
    "uây", "uôi", "uya", "uyu", "ươi", "ươu",
}
# Bắt buộc có phụ âm cuối.
NEED_FINAL = {"ă", "â", "iê", "yê", "uâ", "uô", "ươ", "oă", "uyê", "oo"}


def _strip(s: str) -> str:
    return "".join(BASE.get(c, c) for c in s)


NUCLEUS_BASE_PREFIXES = {_strip(n)[:i] for n in NUCLEI for i in range(len(n) + 1)}


class _Ch:
    __slots__ = ("c", "upper", "src")

    def __init__(self, c: str, upper: bool, src: str = ""):
        self.c = c          # ký tự thường (đã biến đổi)
        self.upper = upper  # có viết hoa không
        self.src = src      # phím đã tạo ra biến đổi ("w", "[", ...) để hỗ trợ gõ lặp để hủy


def _apply_keys(keys: str):
    chars: list[_Ch] = []
    tone = 0
    blocked: set[str] = set()

    frozen = False   # đã chắc chắn không phải tiếng Việt: các phím sau giữ nguyên

    def vowel_idx():
        return [i for i, ch in enumerate(chars) if ch.c in VOWELS]

    for k in keys:
        lo = k.lower()
        up = k != lo

        if not frozen and chars and not _could_be_syllable("".join(ch.c for ch in chars)):
            frozen = True
        if frozen:
            chars.append(_Ch(lo, up))
            continue

        if lo in TONE_KEYS or lo == "z":
            if lo == "z":
                if tone and vowel_idx():
                    tone = 0
                    continue
                chars.append(_Ch(lo, up))
                continue
            t = TONE_KEYS[lo]
            if vowel_idx() and lo not in blocked:
                if tone == t:           # gõ lặp: hủy dấu, giữ phím
                    tone = 0
                    blocked.add(lo)
                    chars.append(_Ch(lo, up))
                else:
                    tone = t
                continue
            chars.append(_Ch(lo, up))
            continue

        if lo == "d":
            # "d" không bao giờ là phụ âm cuối, nên "d" gõ sau (ở bất kỳ đâu trong từ)
            # chỉ có thể là biến d đầu từ thành đ: ddi, did, dudocwj…
            if chars and chars[0].c == "d" and "d" not in blocked:
                chars[0].c = "đ"
                continue
            if chars and chars[0].c == "đ":     # gõ lặp: đ + d -> dd
                chars[0].c = "d"
                blocked.add("d")
            chars.append(_Ch(lo, up))
            continue

        if lo in CIRCUMFLEX:
            if lo not in blocked:
                hit = None
                for i in reversed(vowel_idx()):
                    if chars[i].c in (lo, CIRCUMFLEX[lo]):
                        hit = i
                        break
                if hit is not None and chars[hit].c == lo:
                    chars[hit].c = CIRCUMFLEX[lo]
                    continue
                if hit is not None and chars[hit].c == CIRCUMFLEX[lo]:
                    chars[hit].c = lo           # gõ lặp: hủy mũ
                    blocked.add(lo)
            chars.append(_Ch(lo, up))
            continue

        if lo == "w":
            if "w" in blocked:
                chars.append(_Ch(lo, up))
                continue
            vi = vowel_idx()
            # 1) Thử biến đổi: uo -> ươ, nếu còn ký tự chưa đổi.
            pair = None
            for a, b in zip(vi, vi[1:]):
                if b == a + 1 and chars[a].c in ("u", "ư") and chars[b].c in ("o", "ơ"):
                    pair = (a, b)
            if pair and (chars[pair[0]].c, chars[pair[1]].c) != ("ư", "ơ"):
                for i, new in zip(pair, ("ư", "ơ")):
                    if chars[i].c != new:
                        chars[i].c, chars[i].src = new, "w"
                continue
            # 2) a/o/u chưa biến đổi -> ă/ơ/ư. Ưu tiên lựa chọn cho ra vần hợp lệ
            #    (chuaw -> chưa, không phải chuă; quaw -> quă vì "qu" là phụ âm đầu).
            options = [i for i in reversed(vi)
                       if chars[i].c in ("a", "o", "u") and not (pair and i in pair)]
            target = None
            for i in options:
                trial = [ch.c for ch in chars]
                trial[i] = {"a": "ă", "o": "ơ", "u": "ư"}[trial[i]]
                if _nucleus_could_be("".join(trial)):
                    target = i
                    break
            if target is None and options:
                target = options[0]
            if target is not None:
                chars[target].c = {"a": "ă", "o": "ơ", "u": "ư"}[chars[target].c]
                chars[target].src = "w"
                continue
            # 3) Không còn gì để biến đổi: gõ lặp để hủy.
            made = [ch for ch in chars if ch.src in ("w", "w0")]
            if made:
                blocked.add("w")
                if len(made) == 1 and made[0].src == "w0" and made[0] is chars[-1]:
                    made[0].c, made[0].src = "w", ""      # ww -> w
                    continue
                for ch in made:
                    ch.c = {"ă": "a", "ơ": "o", "ư": "u"}[ch.c]
                    ch.src = ""
                chars.append(_Ch(lo, up))
                continue
            # 4) w đứng riêng (chưa có nguyên âm) -> ư.
            if not vi:
                chars.append(_Ch("ư", up, "w0"))
                continue
            chars.append(_Ch(lo, up))
            continue

        if k in "[]{}":
            new = {"[": "ơ", "]": "ư", "{": "ơ", "}": "ư"}[k]
            if chars and chars[-1].src == k:      # gõ lặp: [[ -> [
                chars[-1].c, chars[-1].src = k, ""
                continue
            chars.append(_Ch(new, k in "{}", k))
            continue

        chars.append(_Ch(lo, up))

    return chars, tone


def _split(s: str):
    """Tách âm tiết (chữ thường, chưa có dấu thanh) thành (đầu, vần, cuối). None nếu không tách được."""
    initial = ""
    for ini in INITIALS:
        if s.startswith(ini):
            rest = s[len(ini):]
            if ini == "gi" and not (rest and rest[0] in VOWELS):
                continue   # "gì", "gin": i là nguyên âm
            if ini == "qu" and rest and rest[0] not in VOWELS:
                continue
            initial = ini
            break
    rest = s[len(initial):]
    i = 0
    while i < len(rest) and rest[i] in VOWELS:
        i += 1
    nucleus, final = rest[:i], rest[i:]
    if any(c in VOWELS for c in final):
        return None
    if not nucleus and final:
        return None
    if not initial and s and s[0] not in VOWELS:
        return None   # phụ âm đầu không hợp lệ (f, j, w, z, cl…)
    return initial, nucleus, final


def _could_be_syllable(s: str) -> bool:
    """Chuỗi (chưa dấu thanh) có thể là phần đầu của một âm tiết hợp lệ không."""
    if s == "q":
        return True   # phần đầu của "qu"
    parts = _split(s)
    if parts is None:
        return False
    _, nucleus, final = parts
    return (
        _strip(nucleus) in NUCLEUS_BASE_PREFIXES
        and final in FINAL_PREFIXES
        and not (final and nucleus in OPEN_ONLY)
    )


NUCLEUS_PREFIXES = {n[:i] for n in NUCLEI for i in range(len(n) + 1)}


def _nucleus_could_be(s: str) -> bool:
    """Vần (giữ nguyên dấu mũ/móc) có thể là phần đầu của một vần hợp lệ không."""
    parts = _split(s)
    return parts is not None and parts[1] in NUCLEUS_PREFIXES


def _tone_index(nucleus: str, has_final: bool, new_style: bool) -> int:
    if "ươ" in nucleus:
        return nucleus.index("ươ") + 1
    marked = [i for i, c in enumerate(nucleus) if c in HORN_DIACRITICS]
    if marked:
        return marked[-1]
    if len(nucleus) == 1:
        return 0
    if has_final:
        return len(nucleus) - 1
    if len(nucleus) == 3:
        return 1
    if new_style and nucleus in ("oa", "oe", "uy"):
        return 1
    return 0


def _render(keys: str, strict: bool, new_style: bool) -> str:
    chars, tone = _apply_keys(keys)
    # Chuẩn hóa cặp u/o có móc để thứ tự đặt w không quan trọng:
    # - còn chữ phía sau -> "ươ" (được, người, mượn…)
    # - đứng cuối từ     -> "uơ" (thuở, huơ), vì "ươ" không bao giờ đứng cuối.
    for i in range(len(chars) - 1):
        pair = (chars[i].c, chars[i + 1].c)
        if pair in (("ư", "o"), ("u", "ơ"), ("ư", "ơ")):
            chars[i].c = "ư" if i + 2 < len(chars) else "u"
            chars[i + 1].c = "ơ"
    plain = "".join(ch.c for ch in chars)
    if not plain:
        return ""

    def cased(out):
        return "".join(c.upper() if ch.upper else c for c, ch in zip(out, chars))

    # Kết quả không có gì "tiếng Việt" (ví dụ sau khi gõ lặp để hủy: ass -> as, ww -> w):
    # giữ nguyên, không khôi phục về phím gốc.
    if not tone and plain.isascii():
        return cased(list(plain))

    parts = _split(plain)
    if parts is None:
        return keys
    initial, nucleus, final = parts

    if strict:
        # Ghi chú: không bắt NEED_FINAL ("â", "tiê"…) để tránh khôi phục khó chịu;
        # từ tiếng Anh hiếm khi tạo ra các vần này.
        ok = (
            (nucleus in NUCLEI or not nucleus and not final and initial)
            and (not final or final in FINALS)
            and not (final and nucleus in OPEN_ONLY)
            and not (final in STOP_FINALS and tone in (2, 3, 4))
            and not (tone and not nucleus)
        )
    else:
        ok = (
            _strip(nucleus) in NUCLEUS_BASE_PREFIXES
            and final in FINAL_PREFIXES
            and not (final and nucleus in OPEN_ONLY)
            and not (final and final[0] in "cpt" and tone in (2, 3, 4))
        )
    if not ok:
        return keys

    out = [ch.c for ch in chars]
    if tone and nucleus:
        start = len(initial)
        i = start + _tone_index(nucleus, bool(final), new_style)
        out[i] = TONED[out[i]][tone]
    return cased(out)


def transform(keys: str, new_style: bool = False) -> str:
    return _render(keys, strict=False, new_style=new_style)


def finalize(keys: str, new_style: bool = False) -> str:
    return _render(keys, strict=True, new_style=new_style)
