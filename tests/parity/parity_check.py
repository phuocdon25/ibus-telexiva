#!/usr/bin/env python3
"""So khớp core C++ với prototype Python (oracle) trên rất nhiều chuỗi phím.

Chạy (CTest tự gọi):
    python3 tests/parity/parity_check.py build/debug/telexiva-telex

Nguồn chuỗi phím (cố định, không cần mạng hay file ngoài):
  - mọi tổ hợp phụ âm đầu x vần x phụ âm cuối x thanh, mỗi tổ hợp vài kiểu thứ tự gõ;
  - chuỗi ngẫu nhiên (seed cố định) thiên về các phím Telex;
  - từ tiếng Anh trong từ điển máy (nếu có), để kiểm tra phần khôi phục.
So sánh 4 kết quả: transform/finalize x kiểu dấu cũ/mới.
"""

from __future__ import annotations

import os
import random
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "prototype"))

import telex  # noqa: E402
from wordlist_check import variants  # noqa: E402


def synthetic_syllables():
    inputs = set()
    initials = [""] + list(telex.INITIALS)
    finals = [""] + sorted(telex.FINALS)
    for ini in initials:
        for nuc in telex.NUCLEI:
            for fin in finals:
                plain = ini + nuc + fin
                if not telex._is_valid_syllable(plain):
                    continue
                for tone in range(6):
                    if fin in telex.STOP_FINALS and tone in (2, 3, 4):
                        continue
                    for keys in variants(list(plain), tone).values():
                        inputs.add(keys)
                        inputs.add(keys[0].upper() + keys[1:])
    return inputs


def random_keys(n=30000, seed=20261110):
    rng = random.Random(seed)
    alphabet = "aeiouydwsfrxjzqcgnhtmplbkv[]{}" + "aeiouwsfrxjd" * 2
    out = set()
    while len(out) < n:
        k = "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 9)))
        if rng.random() < 0.15:
            k = k.capitalize()
        out.add(k)
    return out


def english_words(limit=30000):
    words = sorted(w for w in telex._english() if w.isalpha() and len(w) <= 12)
    return set(words[:limit])


def sentences(n=4000, seed=20261111):
    """Câu gõ hỗn hợp: âm tiết tiếng Việt (nhiều thứ tự gõ), từ tiếng Anh, code, URL,
    email, số và dấu câu — để so khớp Composer (C++) với engine Python ở mức câu."""
    rng = random.Random(seed)
    viet = sorted(synthetic_syllables())
    eng = sorted(english_words(5000)) or ["const", "error", "test"]
    seps = [" ", " ", " ", ", ", ". ", "_", "/", "@", ".", "-", "=", " $", ": ", "! "]
    out = []
    for _ in range(n):
        words = []
        for _ in range(rng.randint(1, 8)):
            r = rng.random()
            if r < 0.6:
                words.append(rng.choice(viet))
            elif r < 0.85:
                words.append(rng.choice(eng))
            else:
                words.append(str(rng.randint(0, 2000000)))
            words.append(rng.choice(seps))
        out.append("".join(words) + " ")
    return out


def check_compose(cli):
    sys.path.insert(0, os.path.join(HERE, "..", "..", "prototype"))
    import test_engine_sim as sim   # engine Python + ô nhập giả (cần gi/IBus)
    sim.T.LOG.disabled = True
    inputs = sentences()
    proc = subprocess.run([cli, "--compose"], input="\n".join(inputs) + "\n", capture_output=True,
                          text=True, encoding="utf-8", check=True)
    lines = proc.stdout.splitlines()
    bad = []
    for keys, line in zip(inputs, lines):
        cpp = line.split("\t", 1)[1]
        py = sim.FakeApp().type(keys).buf
        if cpp != py:
            bad.append((keys, py, cpp))
    print(f"Parity (câu, --compose): {len(inputs)} câu, {len(bad)} khác biệt")
    for keys, py, cpp in bad[:10]:
        print(f"  {keys!r}\n    py ={py!r}\n    cpp={cpp!r}")
    return not bad


def python_results(keys):
    return (telex.transform(keys), telex.finalize(keys),
            telex.transform(keys, new_style=True), telex.finalize(keys, new_style=True))


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    cli = sys.argv[1]
    t0 = time.time()
    inputs = sorted(synthetic_syllables() | random_keys() | english_words())
    inputs = [k for k in inputs if k and "\t" not in k and "\n" not in k]

    proc = subprocess.run([cli], input="\n".join(inputs) + "\n", capture_output=True,
                          text=True, encoding="utf-8", check=True)
    lines = proc.stdout.splitlines()
    if len(lines) != len(inputs):
        print(f"Số dòng C++ ({len(lines)}) khác số input ({len(inputs)})")
        sys.exit(1)

    mismatches = []
    for keys, line in zip(inputs, lines):
        cols = line.split("\t")
        cpp = tuple(cols[1:5])
        py = python_results(keys)
        if cols[0] != keys or cpp != py:
            mismatches.append((keys, py, cpp))

    print(f"Parity: {len(inputs)} chuỗi phím, {len(mismatches)} khác biệt ({time.time() - t0:.1f}s)")
    labels = ("transform", "finalize", "transform(new)", "finalize(new)")
    for keys, py, cpp in mismatches[:20]:
        diff = ", ".join(f"{lab}: py={p!r} cpp={c!r}" for lab, p, c in zip(labels, py, cpp) if p != c)
        print(f"  {keys!r}: {diff}")
    compose_ok = check_compose(cli)
    sys.exit(1 if mismatches or not compose_ok else 0)


if __name__ == "__main__":
    main()
