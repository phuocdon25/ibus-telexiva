#!/usr/bin/env bash
# Cài Telexiva prototype vào IBus (chạy song song với ibus-unikey, không đụng tới nó).
# Chỉ chép một file khai báo vào /usr/share/ibus/component/ — cần sudo cho bước này.
# Engine chạy thẳng từ thư mục repo, nên sửa code xong chỉ cần `ibus restart`.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$HERE/telexiva_proto.py"
TARGET=/usr/share/ibus/component/telexiva-proto.xml
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

python3 -m unittest discover -s "$HERE" >/dev/null 2>&1 || {
  echo "Unit test thất bại, dừng cài đặt. Chạy: python3 -m unittest discover -s $HERE -v" >&2
  exit 1
}

sed "s#@SCRIPT@#$SCRIPT#" "$HERE/telexiva-proto.xml.in" > "$TMP"
echo "Chép file khai báo engine vào $TARGET (cần sudo)…"
sudo install -m 644 "$TMP" "$TARGET"

# Không cần `ibus write-cache`: daemon tự quét lại component khi khởi động lại.
ibus restart
echo
echo "Xong. Thêm bộ gõ: Settings → Keyboard → Input Sources → + → Vietnamese → Telexiva (prototype)"
echo "Chuyển qua lại với Unikey bằng Super+Space."
echo "Log (không chứa nội dung gõ): ~/.cache/telexiva-proto/engine.log"
