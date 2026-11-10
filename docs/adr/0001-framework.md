# ADR 0001: Telexiva là một IBus engine

| | |
|---|---|
| Trạng thái | Đã chấp nhận |
| Ngày | 2026-11-10 |
| Liên quan | [requirement.md](../../requirement.md) §6.0, FR-009, FR-010 |

## Bối cảnh

Telexiva nhắm tới Ubuntu 26.04 với GNOME trên Wayland. Người dùng chính làm việc trong Chrome 148 (chạy native Wayland) và VS Code. Trên Linux có hai input method framework phổ biến: IBus và Fcitx5.

Các yếu tố đã xem xét:

- **GNOME/Mutter chỉ chuyển input từ giao thức Wayland `text-input-v3` sang IBus.** Fcitx5 chỉ nhận được phím trên GNOME qua IM module GTK/Qt mà ứng dụng tự nạp. Nó cũng cần extension Kimpanel (không có trong kho Ubuntu 26.04) để hiện trạng thái.
- Nhận định "Fcitx5 hỗ trợ Wayland tốt hơn" (ví dụ trong README của `ibus-bamboo`) đúng với KDE, Sway, Hyprland, những nơi Fcitx5 dùng được giao thức `input-method`. Nó không đúng với GNOME. Các nguồn người dùng tham khảo cũng kết luận IBus phù hợp hơn với GNOME Wayland.
- Người dùng đang dùng `ibus-unikey`. Một IBus engine mới chỉ cần thêm vào danh sách input source, chạy song song và so sánh được bằng `Super+Space`, không cần đổi `im-config`.
- `ibus-bamboo` đã đình trệ; `ibus-unikey` là bản beta cũ, dùng preedit.

## Quyết định

Telexiva được xây dựng như một **IBus engine**. Phần xử lý tiếng Việt (core) độc lập với IBus, để sau này có thể viết thêm frontend Fcitx5 cho các desktop khác.

## Hệ quả

### Tích cực

- Tích hợp native với GNOME: có trong Settings → Keyboard → Input Sources, chuyển bằng `Super+Space`.
- Nhận phím từ Chrome và VS Code chạy native Wayland, qua đường Mutter → IBus.
- Cài đặt rủi ro thấp: chỉ thêm một component, không đụng tới `ibus-unikey` hay `im-config`.

### Tiêu cực / ràng buộc

- API của IBus là C/GObject. Bản C++ cần một lớp wrapper RAII mỏng.
- IBus không tự sinh giao diện cấu hình, nên phải tự viết ứng dụng settings (FR-007).
- Mọi ràng buộc của đường Mutter → IBus đều áp vào Telexiva (xem phần kiểm chứng bên dưới).

## Kiểm chứng ở Phase 0 (prototype Python)

Chi tiết trong [docs/findings/](../findings/).

| Câu hỏi | Kết quả |
|---|---|
| Chrome Wayland có cung cấp surrounding text qua IBus không? | **Có**, với ô nhập thường. Ô soạn thảo nâng cao (ChatGPT, Gemini) **bỏ qua** `delete_surrounding_text`. |
| `forward_key_event` (Backspace giả) có dùng được không? | **Không**: trên Wayland phím forward không tới ứng dụng nào. |
| Engine có biết đang gõ trong ứng dụng nào không? | **Không**: client luôn là `gnome-shell`. Chỉ ứng dụng nối thẳng qua IM module (ví dụ Chrome XWayland: `gtk3-im:google-chrome`) mới có tên. |
| Chrome XWayland có phải lối thoát không? | **Không**: không có surrounding text; Backspace giả bị đảo thứ tự với commit; keysym có dấu bị bỏ qua. |
| "Pass-through first" có sửa được lỗi ban đầu không? | **Có** với BUG-003 (người dùng xác nhận). Baseline chỉ ra BUG-001/002/004 do preedit; chờ đo lại bằng playground. |

Các kết quả này không làm thay đổi quyết định chọn IBus: với Fcitx5 trên GNOME, đường đi vào Chrome Wayland còn bị hạn chế hơn. Chúng định hình lại FR-009 (S2 mặc định, S1 tự động, bỏ S3) và FR-010 (hạ xuống P2).

## Phương án đã cân nhắc

| Phương án | Lý do không chọn |
|---|---|
| Fcitx5 addon | Không nhận được phím từ ứng dụng dùng `text-input-v3` trên GNOME; cần extension ngoài kho |
| Viết cả hai frontend ngay từ đầu | Gấp đôi công sức trong khi người dùng chỉ dùng GNOME; core độc lập đã đủ để mở rộng sau |
| Sửa trực tiếp `ibus-unikey` | Không đúng mục tiêu học tập; mã cũ, dùng preedit theo thiết kế |
