#!/usr/bin/env python3
"""Xuất các bảng test do người viết (prototype/test_telex.py) ra tests/data/telex_cases.tsv.

File TSV là nguồn dữ liệu chung: prototype Python và core C++ (tests/core) cùng phải qua.
Chạy lại script này mỗi khi thêm ca test trong test_telex.py:

    python3 tests/data/export_cases.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "prototype"))

import test_telex  # noqa: E402

rows = []  # (hàm, kiểu dấu, phím, mong đợi, nhóm)
for keys, want in test_telex.TelexFinal.CASES:
    rows.append(("finalize", "old", keys, want, "cases"))
for want, variants in test_telex.TelexFinal.ORDERS.items():
    for keys in variants:
        rows.append(("finalize", "old", keys, want, "orders"))
rows += [
    ("finalize", "new", "hoaf", "hoà", "new_style"),
    ("finalize", "new", "thuys", "thuý", "new_style"),
    ("transform", "old", "tiee", "tiê", "typing"),
    ("transform", "old", "nguoiw", "ngươi", "typing"),
    ("transform", "old", "vietj", "viẹt", "typing"),
]
for keys in ["l", "lo", "Q", "loc", "localh"]:
    rows.append(("transform", "old", keys, keys, "pass_through"))

out = os.path.join(HERE, "telex_cases.tsv")
with open(out, "w", encoding="utf-8") as f:
    f.write("# Sinh bởi tests/data/export_cases.py từ prototype/test_telex.py — không sửa tay.\n")
    f.write("# function\tstyle\tkeys\texpected\tgroup\n")
    for r in rows:
        f.write("\t".join(r) + "\n")
print(f"{len(rows)} ca -> {os.path.relpath(out)}")
