# Đối chiếu: Typing Engine Improvement Checklist

Đối chiếu với `Telexiva_Typing_Engine_Improvement_Checklist.md` (2026-11-18). ✅ đã có · 🟡 một phần · ❌ chưa · ➖ không áp dụng.

## Điều chỉnh so với checklist

- Checklist nhắc **Fcitx5** (mục 6, 9). Dự án đã chốt **IBus** (ADR 0001): input context là IBus context, core vẫn độc lập framework.
- Checklist mục 4 đề xuất Backspace có thể "hoàn tác một bước biến đổi". Telexiva chọn **Backspace xóa một ký tự đang hiển thị** (giống UniKey) và vẫn nhớ phần còn lại để sửa dấu; hoàn tác biến đổi làm bằng **gõ lặp phím** (`ass` → `as`) hoặc **Esc** (khôi phục chuỗi phím gốc).
- Checklist mục 6 "state machine Idle/Composing/Committing/Resetting": vì không dùng preedit mặc định, trạng thái thực tế là Idle / Composing (Composer có `raw`) / Frozen (giữ nguyên phần còn lại của từ) / Preedit (ô không đáng tin). Không tạo thêm trạng thái chỉ để khớp tên.
- Checklist mục 9 "replay sự kiện": thay vì ghi phím người dùng (rủi ro riêng tư), việc tái hiện dựa trên **ô nhập giả** (`tests/engine`) + **parity** với prototype + log chỉ có số liệu. Ghi phím thật chỉ nên là tùy chọn người dùng chủ động bật (chưa làm).

## 1. Telex core — ✅

Đủ `aa aw ee oo ow uw dd`, 5 dấu + `z`, thay dấu, dấu trước/sau phụ âm cuối, `iê yê uô ươ ưa uyê`, `qu`/`gi`, kiểu cũ/mới, chữ hoa. Cách thoát: gõ lặp phím (`ass`), **Esc** (mới).

## 2. Phân tích âm tiết — ✅

Tách đầu/vần/cuối; trạng thái chưa hoàn chỉnh (transform "lỏng") và hoàn chỉnh (finalize "chặt"); không phụ thuộc từ điển để chuyển đổi (từ điển tiếng Anh chỉ dùng để *khôi phục*).

## 3. Thứ tự phím — ✅

Nhiều thứ tự gõ (`dudocwj`, `tiengse`, `chuaw`…), 38.264 chuỗi từ Viet74K đúng 100%.

## 4. Backspace, sửa lỗi — 🟡

- ✅ Backspace khi đang gõ vẫn sửa được dấu (`việt` → ⌫ → `việ` → `s` → `viế`).
- ✅ Quay lại từ đã gõ (Space+⌫, click, mũi tên) rồi gõ phím dấu.
- ✅ **Mới:** sửa dấu thanh khi con trỏ ở **giữa từ** (`hoa|ng` + `f` → `hoàng`).
- ✅ Ctrl+Backspace, Delete, Ctrl+Z: engine bỏ từ đang nhớ, không sửa gì (an toàn).
- ❌ Sửa mũ/móc giữa từ (chỉ dấu thanh).

## 5. Tiếng Anh, số, URL, code — ✅

- ✅ Số đi thẳng (BUG-001), URL/email/biến (`foo_bar`, `test@x.com`).
- ✅ **Mới:** từ viết tắt IN HOA (`AWS`, `OS`, `REST`, `CORS`, `UX`…): 26 từ trước đây bị đổi nhầm.
- ✅ **Mới:** Esc khôi phục chuỗi gốc khi đoán sai.
- ✅ **Mới:** Ctrl+Shift chuyển Việt/Anh, không mất nội dung đang soạn.
- ➖ Ngoại lệ theo ứng dụng: GNOME Wayland không cho biết ứng dụng (FR-010).

## 6. Composition — ✅ (IBus)

Context độc lập; không commit trùng (guard + kiểm tra sau khi sửa); Enter/Tab/Esc/mũi tên/phím tắt/focus; ô tự đổi nội dung (`content_changed`); ô không hỗ trợ đầy đủ → tự chuyển nháp.

## 7. Tương thích — 🟡

✅ input/textarea/contenteditable, controlled input, ô tiền tệ, omnibox, VS Code, GTK. ❌ Terminal (ngoài phạm vi theo quyết định của người dùng), Qt/Firefox chưa thử. Regression BUG-001/002/003 có test.

## 8. UX & hiệu năng — 🟡

- ✅ ~0,5 µs/phím (core), không ghi nội dung gõ.
- ✅ **Mới:** biểu tượng **V/E** trên thanh trạng thái GNOME + bấm để chuyển.
- ✅ **Mới:** gõ tắt (`ko` → `không`) từ `~/.config/telexiva/macros.txt`.
- ❌ Ghi nhớ cấu hình theo ứng dụng (không biết ứng dụng trên Wayland).

## 9. Kiến trúc — ✅

Raw keystrokes (Composer), parser/validator/renderer tách hàm, core độc lập IBus, xác định (cùng chuỗi phím → cùng kết quả: parity 231.857 chuỗi), không sửa văn bản đã commit khi không chắc (guard).

## 10. Testing — ✅

Unit + bảng dùng chung + fuzz 50.000 chuỗi + engine với ô nhập giả + parity C++/Python + Viet74K + **CI GitHub Actions (mới)**. ❌ VNI (P2).

## Còn lại đáng làm tiếp

1. Sửa mũ/móc giữa từ (`hoa|ng` + `a`?) — cần quy ước rõ.
2. Settings app (FR-007) để bật/tắt tùy chọn thay vì sửa file.
3. VNI (FR-002) nếu muốn chia sẻ cho người dùng khác.
4. Ghi phím tùy chọn (opt-in) để người dùng gửi báo lỗi tái hiện được.
