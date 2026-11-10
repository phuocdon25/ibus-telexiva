# ibus-telexiva

Bộ gõ tiếng Việt (Telex) cho Linux, chạy dưới dạng engine của [IBus](https://github.com/ibus/ibus). Mục tiêu là gõ giống UniKey trên Windows và ổn định trong trình duyệt và VS Code trên Ubuntu GNOME/Wayland.

> **Trạng thái: thử nghiệm (Phase 0).** Repo hiện có bản prototype viết bằng Python để kiểm chứng thiết kế. Bản chính thức (C++20) chưa bắt đầu. Xem [requirement.md](requirement.md).

## Vì sao có dự án này

Các bộ gõ hiện có như `ibus-unikey` giữ chữ đang gõ ở dạng "nháp" (preedit, chữ có gạch chân) cho tới khi kết thúc từ. Trên Chrome, cách này gây ra các lỗi như:

- ô tiền tệ tự định dạng (`1,200,000`) bị nhân đôi chữ số;
- chọn gợi ý autocomplete bị dư ký tự (`Quên chấm côngQ`);
- thanh địa chỉ không điều hướng tới URL được gợi ý khi nhấn Enter.

Telexiva thử cách **"pass-through first"**: phím không cần biến đổi thì đi thẳng tới ứng dụng như khi gõ tiếng Anh. Chỉ khi cần thêm dấu, engine mới sửa lại chữ vừa gõ. Ô nào không hỗ trợ cách này (ví dụ ô chat ChatGPT, Gemini) thì engine tự chuyển sang dùng nháp. Chi tiết và số liệu nằm trong [docs/findings/](docs/findings/).

## Tính năng (prototype)

- Telex theo hành vi UniKey: gõ dấu tự do (`tieengs`, `tieesng`, `tiengse` đều ra `tiếng`), gõ lặp phím để hủy dấu (`ass` → `as`), `w`/`[`/`]` thành ư/ơ.
- Đặt dấu kiểu cũ (`hòa`) mặc định, có tùy chọn kiểu mới (`hoà`).
- Kiểm tra chính tả và tự khôi phục từ tiếng Anh (`const`, `function`, `error` giữ nguyên).
- Không dùng nháp ở ô thường; tự chuyển sang nháp ở ô không hỗ trợ xóa chữ.
- Không gửi dữ liệu ra mạng; log không ghi nội dung người dùng gõ.

Giới hạn đã biết: từ tiếng Anh trùng với âm tiết tiếng Việt hợp lệ (`test` → `tét`, `var` → `vả`) vẫn bị biến đổi, giống UniKey. Chưa có VNI. Terminal chưa được hỗ trợ.

## Cài thử prototype

Yêu cầu: Ubuntu có IBus, gói `python3-gi` và `gir1.2-ibus-1.0` (thường đã có sẵn), cùng gói `wamerican` (từ điển tiếng Anh, tùy chọn).

```bash
git clone https://github.com/phuocdon25/ibus-telexiva.git
cd ibus-telexiva
./prototype/install.sh      # chạy test, rồi đăng ký engine với IBus (cần sudo một lần)
```

Sau đó vào **Settings → Keyboard → Input Sources → + → Vietnamese → Telexiva (prototype)**, rồi chuyển bộ gõ bằng `Super+Space`. Telexiva chạy song song với `ibus-unikey`, không thay đổi gì của bộ gõ đó.

Gỡ cài đặt: xóa Telexiva khỏi Input Sources, rồi chạy `./prototype/uninstall.sh`.

Chi tiết về cấu hình và log nằm trong [prototype/README.md](prototype/README.md).

## Kiểm thử

```bash
python3 -m unittest discover -s prototype -v          # unit test + mô phỏng engine
python3 prototype/run_user_cases.py                   # các ca trong vietnamese-telex-test-cases.md
python3 prototype/wordlist_check.py <danh-sách-từ.txt> # kiểm tra hàng loạt với một danh sách từ tiếng Việt
```

Khi test thủ công trên trình duyệt, dùng [tools/playground/index.html](tools/playground/index.html). Trang này ghi lại chuỗi sự kiện bàn phím và IME của từng ô nhập.

## Cấu trúc

| Đường dẫn | Nội dung |
|---|---|
| [requirement.md](requirement.md) | Đặc tả, quyết định kiến trúc, lộ trình |
| [docs/findings/](docs/findings/) | Kết quả các lần thử nghiệm |
| [prototype/](prototype/) | Engine IBus bằng Python (Phase 0) |
| [tools/playground/](tools/playground/) | Trang HTML để test bộ gõ trên trình duyệt |
| [vietnamese-telex-test-cases.md](vietnamese-telex-test-cases.md) | Bộ ca kiểm thử Telex |

## Giấy phép

[GPL-3.0-or-later](LICENSE).
