# Prototype Python: những gì học được ở lần chạy đầu

| | |
|---|---|
| Ngày | 2026-11-10 |
| Môi trường | Ubuntu 26.04, GNOME Wayland, Chrome 148, VS Code 1.120, IBus 1.5.34 |
| Engine | `prototype/telexiva_proto.py` (pass-through first, S2/S3, guard) |
| Nguồn | Trải nghiệm thực tế của người dùng + `~/.cache/telexiva-proto/engine.log` |

## Kết quả chính

1. **Pass-through first chạy được trên GNOME Wayland.** Gõ tiếng Việt hằng ngày trong VS Code (ô chat) và Chrome bằng S2 (`delete_surrounding_text` + `commit_text`), không có preedit. Người dùng đánh giá "có vẻ ổn hơn" sau các bản sửa bên dưới.

2. **S3 (giả lập Backspace) không hoạt động trong terminal trên GNOME Wayland.**
   Gõ `nguyeenx` trong terminal ra `nguyeênx`: `forward_key_event(BackSpace)` được gửi (`replace strategy=s3 del=1`) nhưng terminal không xóa ký tự nào. Hệ quả: FR-009 không thể dựa vào S3 làm phương án dự phòng chung. Terminal được xếp ưu tiên thấp (người dùng gần như không gõ tiếng Việt trong terminal). Cần nghiên cứu thêm (ví dụ commit ký tự DEL cho terminal) trước khi kết luận.

3. **Engine không biết đang ở ứng dụng nào.** Với `has-focus-id`, tên client mà IBus báo luôn là `gnome-shell` (ứng dụng Wayland đi qua Mutter) hoặc `fake` (context ảo của IBus). FR-010 (cấu hình theo ứng dụng) không thể dựa vào tên client trên GNOME Wayland; phải dựa vào capability, purpose/hints, hoặc cách khác (ví dụ extension GNOME Shell báo cửa sổ đang focus).

4. **Surrounding text không phải lúc nào cũng đáng tin, guard là bắt buộc nhưng phải "khoan dung" có kiểm soát:**
   - **Báo trễ khi gõ nhanh:** `macwj` ra `măcj`. Guard giờ chấp nhận 2 trạng thái gần nhất của từ.
   - **Vùng chọn sau con trỏ** (inline autocomplete của omnibox) không được chặn biến đổi.
   - **VS Code trên GNOME Wayland báo cursor lệch anchor** dù không có vùng chọn. Độ lệch quan sát được khớp với số byte UTF-8 dư của từ đang gõ (ví dụ `đươc`: lệch 3). Giả thuyết: một vị trí bị tính theo byte. Guard đối chiếu thêm theo anchor và log `matched_by=anchor` để kiểm chứng. **Chưa xác nhận.**
   - Khi guard chặn: cho các phím còn lại của từ đi thẳng (không chèn sai), thay vì bắt đầu từ mới.

5. **Telex cần chấp nhận nhiều thứ tự gõ.** Người dùng gõ `dudocwj`, `chuaw`, các biến thể `w`/`d` đặt ở nhiều vị trí. Đã thêm: `d` ở bất kỳ đâu biến `d` đầu từ thành `đ`; chuẩn hóa `ưo/uơ/ươ` theo vị trí; `w` chọn nguyên âm cho ra vần hợp lệ (`chuaw` → `chưa`, `quaw` → `quă`). Bảng test thứ tự gõ ở `prototype/test_telex.py`.

## Hệ quả cho requirement

- FR-009: S3 không phải phương án dự phòng đáng tin trên GNOME Wayland; ghi nhận rủi ro, nghiên cứu thêm cho terminal.
- FR-010: không xác định ứng dụng bằng tên client trên GNOME Wayland.
- FR-001: thêm yêu cầu "nhiều thứ tự gõ" và dùng `ukengine` của Unikey làm oracle so sánh tự động ở Phase 1 (đề xuất của người dùng; lưu ý license GPL).
- NFR/Guard: ghi rõ các dạng sai lệch của surrounding text cần chịu được.

## Việc còn mở

- [ ] Xác nhận giả thuyết byte offset của VS Code (chờ `matched_by=anchor` trong log).
- [ ] Chạy playground với prototype (BUG-001/002/004) và thử omnibox thật (BUG-003).
- [ ] Thử VS Code editor (Monaco), không chỉ ô chat.
- [ ] Nghiên cứu cách sửa chữ trong terminal.

## Bổ sung (chiều 2026-11-10): ô soạn thảo "nâng cao" và các cách xóa chữ

| Thử nghiệm | Kết quả |
|---|---|
| S2 trong ô chat ChatGPT, Gemini (Chrome Wayland) | Lệnh xóa bị bỏ qua, chỉ chèn: `taoj` → `taoạo`. Ô nhập thường vẫn đúng. |
| S3 (Backspace giả) trên Chrome/VS Code Wayland | Backspace không tới ứng dụng nào: `vaanx` → `vaâxn`. Loại bỏ. |
| Chrome XWayland (`--ozone-platform=x11`), client `gtk3-im:google-chrome` | Không có surrounding text. Tên ứng dụng **có** (khác Wayland: `gnome-shell`). |
| S3 trên Chrome XWayland | Backspace tới được nhưng đảo thứ tự với commit: `taoj` → `taạ`, `vaanx` → `vâẫ`. |
| S3k (gửi cả chữ mới bằng phím) trên Chrome XWayland | Thứ tự đúng nhưng Chrome bỏ qua keysym có dấu: `taoj` → `to`. |

Kết luận: trên GNOME Wayland, xóa chữ chỉ có S2; ô soạn thảo nâng cao (ProseMirror…) bỏ qua S2. Hướng tiếp theo: tự phát hiện ô bỏ qua lệnh xóa và chuyển sang preedit (S1) cho ô đó. Bộ quy tắc Telex đã qua 38.378 ca từ danh sách Viet74K (`prototype/wordlist_check.py`).
