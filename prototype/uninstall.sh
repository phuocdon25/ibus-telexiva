#!/usr/bin/env bash
# Gỡ Telexiva prototype. Trước đó nên xóa nó khỏi Settings → Keyboard → Input Sources.
set -euo pipefail

TARGET=/usr/share/ibus/component/telexiva-proto.xml
if [[ -f "$TARGET" ]]; then
  echo "Xóa $TARGET (cần sudo)…"
  sudo rm -f "$TARGET"
fi
ibus write-cache
ibus restart
echo "Đã gỡ. Log cũ (nếu muốn xóa): rm -rf ~/.cache/telexiva-proto"
