#!/usr/bin/env python3
"""Chạy các ca kiểm thử trong vietnamese-telex-test-cases.md qua bộ Telex của prototype.

Chạy: python3 prototype/run_user_cases.py [đường_dẫn_file.md]

Chỉ chạy được các ca có input/expected cụ thể (mục 3, 4, 5, 6, 7, 9). Các ca về
Backspace, con trỏ, autocomplete, môi trường (mục 8, 10) cần kiểm tra trên ứng dụng thật.
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from telex import finalize  # noqa: E402

TONE_KEYS = "sfrxj"


def rows(md: str, section_prefix: str):
    """Các dòng bảng (đã tách ô) trong mục bắt đầu bằng '## <section_prefix>'."""
    m = re.search(rf"^## {re.escape(section_prefix)}.*?$(.*?)(?=^## |\Z)", md, re.S | re.M)
    if not m:
        return []
    out = []
    for line in m.group(1).splitlines():
        if line.startswith("|") and not re.match(r"^\|\s*-", line):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            out.append(cells)
    return out[1:]  # bỏ dòng tiêu đề


def keys_of(cell: str) -> list[str]:
    return re.findall(r"`([^`]*)`", cell)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "vietnamese-telex-test-cases.md")
    md = open(path, encoding="utf-8").read()
    results = []   # (id, keys, expected, got, ok, note)

    def check(cid, keys, expected, new_style=False, note=""):
        got = finalize(keys, new_style=new_style)
        results.append((cid, keys, expected, got, got == expected, note))

    # 3. Chữ cái và chữ hoa (bỏ các ca Config có nhiều kết quả)
    for cid, inp, exp, kind in rows(md, "3."):
        if kind == "Strict":
            check(cid, keys_of(inp)[0], exp)

    # 4. Ma trận nguyên âm × thanh điệu
    for cells in rows(md, "4."):
        base, outs = cells[0], cells[1:]
        for tone_key, exp in zip([""] + list(TONE_KEYS), outs):
            check(f"MX-{base}{tone_key or '0'}", base + tone_key, exp)

    # 5. Một từ — nhiều chuỗi phím (ca có khoảng trắng là Negative: bỏ qua ở đây)
    for cid, word, std, variants, _kind in rows(md, "5."):
        for k in keys_of(std) + keys_of(variants):
            if " " in k:
                continue
            check(cid, k, word, note="chuẩn" if k in keys_of(std) else "biến thể")

    # 6. Vị trí dấu. Ghi chú: file gốc đảo nhãn TP-01..04 — hòa/thủy là kiểu CŨ, hoà/thuỷ là kiểu MỚI.
    for cid, inp, exp, conf in rows(md, "6."):
        k = keys_of(inp)[0]
        if exp in ("hoà", "thuỷ"):
            check(cid, k, exp, new_style=True, note="kiểu mới (file ghi nhầm là kiểu cũ)")
        elif exp in ("hòa", "thủy"):
            check(cid, k, exp, new_style=False, note="kiểu cũ (file ghi nhầm là kiểu mới)")
        else:
            check(cid, k, exp)

    # 7. Thay đổi dấu: các ca có kết quả rõ ràng
    for cid, keys, exp in [("CT-01", "asf", "à"), ("CT-02", "asr", "ả"), ("CT-03", "asx", "ã"),
                           ("CT-04", "asj", "ạ"), ("CT-05", "asz", "a"), ("CT-06", "awsz", "ă"),
                           ("CT-09", "ass", "as")]:
        check(cid, keys, exp, note="theo hành vi UniKey")

    # 9. Số, tiếng Anh, URL: gõ ở chế độ tiếng Việt, từng "từ" (tách theo khoảng trắng)
    for cid, inp, _exp in rows(md, "9."):
        ks = keys_of(inp)
        if not ks:
            continue
        text = ks[0]
        for word in re.findall(r"[A-Za-z\[\]{}]+|[^A-Za-z\[\]{}]+", text):
            if re.match(r"[A-Za-z]", word):
                check(cid, word, word, note=f"trong '{text}' (chế độ tiếng Việt)")

    fails = [r for r in results if not r[4]]
    print(f"File: {os.path.relpath(path)}")
    print(f"Đã chạy {len(results)} ca: {len(results) - len(fails)} đúng, {len(fails)} sai\n")
    for cid, keys, exp, got, _, note in fails:
        print(f"  ✗ {cid:10} {keys:16} -> {got:16} (mong đợi: {exp}) {note}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
