# Telexiva prototype (Phase 0)

IBus engine viết bằng Python để kiểm chứng FR-009 "pass-through first" trước khi viết bản C++. **Không dùng hằng ngày**: Telex chỉ ở mức tối giản, Backspace sẽ kết thúc từ đang gõ.

## Cách hoạt động

- Phím không cần biến đổi (số, `l`, `o`, `Q`…) đi thẳng tới ứng dụng như khi gõ English.
- Phím cần biến đổi thì engine xóa phần chữ cũ rồi đưa chữ mới vào ngay, **không có chữ nháp (preedit)**:
  - Ô nhập hỗ trợ surrounding text (Chrome, ứng dụng GTK): xóa bằng `delete_surrounding_text` (S2).
  - Terminal: gửi phím Backspace giả (S3).
- Trước khi xóa, engine kiểm tra chữ trước con trỏ có đúng là chữ nó vừa gõ không (guard). Nếu trang đã tự đổi nội dung, engine bỏ qua và không xóa gì.

## Cài đặt

```bash
./prototype/install.sh      # chạy unit test, rồi chép 1 file khai báo vào /usr/share/ibus/component (cần sudo)
```

Sau đó vào **Settings → Keyboard → Input Sources → + → Vietnamese → Telexiva (prototype)**. Dùng `Super+Space` để chuyển qua lại với Unikey. `ibus-unikey` không bị thay đổi gì.

Engine chạy thẳng từ thư mục repo: sửa code xong chỉ cần `ibus restart`.

## Kiểm thử với playground

1. Mở `tools/playground/index.html` trong Chrome.
2. Chuyển sang Telexiva (prototype), chọn "Bộ gõ đang test" là **telexiva-prototype**.
3. Gõ lại các ô giống lượt test của `ibus-unikey` (xem `docs/findings/`).
4. Copy Markdown và lưu vào `docs/findings/logs/`.

Kiểm tra thêm: omnibox thật của Chrome (`lo` + Enter), terminal (GNOME Terminal/Ptyxis), terminal tích hợp của VS Code.

## Cấu hình (tùy chọn)

`~/.config/telexiva-proto.conf`:

```ini
strategy = auto   # auto | s2 | s3
guard    = strict # strict | log | off
tone     = old    # old (hòa) | new (hoà)
```

Đổi cấu hình xong chạy `ibus restart`.

## Log

`~/.cache/telexiva-proto/engine.log`. Log chỉ ghi loại sự kiện, độ dài, strategy và capability của ứng dụng, **không ghi nội dung gõ**. Các dòng đáng chú ý:

- `focus_in caps=… surrounding=True/False strategy=s2/s3`: ứng dụng có hỗ trợ surrounding text không.
- `guard mismatch`: guard đã chặn một lần xóa.

## Test

```bash
python3 -m unittest discover -s prototype -v
```

- `test_telex.py`: quy tắc Telex.
- `test_engine_sim.py`: chạy logic engine với một ô nhập giả, không cần IBus daemon.

## Gỡ cài đặt

Xóa Telexiva khỏi Input Sources, rồi chạy:

```bash
./prototype/uninstall.sh
```
