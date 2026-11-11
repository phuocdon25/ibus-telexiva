#!/usr/bin/env bash
# Build bản release và đăng ký engine C++ với IBus (chạy song song với prototype Python và ibus-unikey).
# Chỉ chép một file khai báo vào /usr/share/ibus/component/ (cần sudo). Engine chạy thẳng từ
# build/release, nên build lại xong chỉ cần `ibus restart`.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
cmake --preset release >/dev/null
cmake --build --preset release
ctest --preset release -LE slow

EXEC="$ROOT/build/release/ibus-engine-telexiva"
TARGET=/usr/share/ibus/component/telexiva.xml
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT
sed "s#@EXEC@#$EXEC#" data/ibus/telexiva.xml.in > "$TMP"
echo "Chép file khai báo engine vào $TARGET (cần sudo)…"
sudo install -m 644 "$TMP" "$TARGET"
ibus restart
echo
echo "Xong. Thêm bộ gõ: Settings → Keyboard → Input Sources → + → Vietnamese → Telexiva (C++)"
echo "Log (không chứa nội dung gõ): ~/.cache/telexiva/engine.log"
