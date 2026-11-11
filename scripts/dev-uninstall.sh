#!/usr/bin/env bash
# Gỡ engine C++. Trước đó nên xóa "Telexiva (C++)" khỏi Settings → Keyboard → Input Sources.
set -euo pipefail
TARGET=/usr/share/ibus/component/telexiva.xml
[[ -f "$TARGET" ]] && sudo rm -f "$TARGET"
ibus restart
echo "Đã gỡ. Log cũ (nếu muốn xóa): rm -rf ~/.cache/telexiva"
