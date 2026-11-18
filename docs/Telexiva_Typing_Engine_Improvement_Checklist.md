# Telexiva — Typing Engine Improvement Checklist

> **Giai đoạn:** Sau MVP · **Mục tiêu:** Nâng độ chính xác, khả năng sửa lỗi và tính tương thích của bộ gõ tiếng Việt native trên Ubuntu.
>
> **Quy ước ưu tiên:** **P0** = ảnh hưởng trực tiếp đến gõ đúng/không mất ký tự; **P1** = cải thiện trải nghiệm; **P2** = mở rộng.

## 1. Telex core & quy tắc chuyển đổi — P0

- [ ] Hoàn thiện `aa → â`, `aw → ă`, `ee → ê`, `oo → ô`, `ow → ơ`, `uw → ư`, `dd → đ`.
- [ ] Hoàn thiện năm dấu thanh `s/f/r/x/j`, xóa dấu `z` và thay dấu đã gõ.
- [ ] Xử lý dấu gõ trước/sau phụ âm cuối; ví dụ `tieengs`, `tieesng` → `tiếng`.
- [ ] Xử lý nguyên âm đôi/ba: `iê`, `yê`, `uô`, `ươ`, `ưa`, `uyê`.
- [ ] Đặt dấu đúng với `qu`, `gi` và các cấu trúc âm tiết đặc biệt.
- [ ] Hỗ trợ quy tắc đặt dấu kiểu cũ/mới theo cấu hình.
- [ ] Bảo toàn chữ hoa, chữ thường, chữ hoa xen kẽ.
- [ ] Quy định rõ cách thoát chuyển đổi để giữ ký tự Telex nguyên bản.

## 2. Phân tích âm tiết tiếng Việt — P0

- [ ] Tách âm đầu, âm đệm, âm chính, âm cuối.
- [ ] Mô hình hóa tổ hợp nguyên âm, phụ âm đầu/cuối hợp lệ.
- [ ] Phân biệt vai trò của `i/y/u` và nguyên âm nhận dấu.
- [ ] Chấp nhận trạng thái âm tiết **chưa hoàn chỉnh** khi đang gõ.
- [ ] Phân loại: hợp lệ / chưa hoàn chỉnh / không hợp lệ.
- [ ] Có chế độ kiểm tra nghiêm ngặt hoặc linh hoạt; không chặn quá sớm.
- [ ] Tránh phụ thuộc hoàn toàn vào từ điển để quyết định chuyển đổi.

## 3. Thứ tự phím và cách gõ đặc biệt — P0–P1

- [ ] Hỗ trợ nhiều thứ tự gõ tạo cùng một âm tiết.
- [ ] Gõ dấu trước/sau khi hoàn thiện nguyên âm đôi hoặc phụ âm cuối.
- [ ] Thay dấu nhiều lần; xóa dấu rồi thêm dấu mới.
- [ ] Xử lý nhiều phím dấu hoặc phím biến đổi liên tiếp.
- [ ] Phân biệt phím Telex là lệnh hay ký tự thường theo ngữ cảnh.
- [ ] Xử lý chuỗi gõ sai, chuỗi lạ và cách nhập không chuẩn một cách dự đoán được.

## 4. Backspace, sửa lỗi, Undo — P0

- [ ] Định nghĩa rõ Backspace xóa một ký tự hay hoàn tác một bước biến đổi.
- [ ] Cho phép sửa dấu mà không xóa và gõ lại toàn bộ âm tiết.
- [ ] Hoàn tác `a → â/ă`, `d → đ` và các biến đổi dấu.
- [ ] Backspace liên tục không làm mất hoặc lặp ký tự.
- [ ] Xử lý Delete, Ctrl+Backspace, Undo/Redo của ứng dụng.
- [ ] Sửa giữa từ, di chuyển con trỏ và chọn vùng văn bản không làm sai trạng thái.
- [ ] Có rollback an toàn khi quy tắc mới không còn phù hợp.

## 5. Nhập tiếng Anh, số, URL và code — P1

- [ ] Không chuyển đổi số thuần túy hoặc làm lặp ký tự trong ô tiền tệ.
- [ ] Giảm chuyển đổi nhầm tiếng Anh và từ viết tắt (`API`, `HTTP`, `JSON`, `CSS`).
- [ ] Không làm hỏng URL, email, đường dẫn, tên biến và đoạn code.
- [ ] Có thao tác khôi phục chuỗi nguyên bản khi engine đoán sai.
- [ ] Cấu hình chế độ linh hoạt / nghiêm ngặt và ngoại lệ theo ứng dụng.
- [ ] Chuyển English/Telex/VNI không làm mất nội dung đang soạn.

## 6. Composition, preedit, commit và focus — P0

- [ ] Thiết kế state machine rõ ràng cho Idle / Composing / Committing / Resetting.
- [ ] Mỗi Fcitx5 input context có trạng thái độc lập.
- [ ] Đồng bộ raw input, preedit hiển thị và nội dung đã commit.
- [ ] Không commit trùng, không mất ký tự, không để ký tự dư.
- [ ] Xử lý Enter, Tab, Escape, mũi tên, phím tắt và chuyển focus.
- [ ] Xử lý ứng dụng tự thay đổi input hoặc không hỗ trợ preedit đầy đủ.
- [ ] Reset/cancel an toàn khi đổi tab, đổi ô nhập hoặc đóng context.

## 7. Tương thích ứng dụng — P0–P1

- [ ] HTML `input`, `textarea`, `contenteditable`.
- [ ] React/Vue controlled inputs và autocomplete.
- [ ] Ô số, tiền tệ và các input có formatter.
- [ ] Chrome omnibox và gợi ý URL.
- [ ] VS Code, terminal, GTK, Qt, Firefox/Chromium.
- [ ] Wayland native và XWayland.
- [ ] Copy/paste, chọn văn bản, di chuyển con trỏ, nhập rất nhanh.

### Regression bắt buộc

- [ ] **BUG-001 — Numeric duplication:** Nhập `1200000` không sinh ký tự lặp.
- [ ] **BUG-002 — Autocomplete:** Chọn `Quên chấm công` không thành `Quên chấm côngQ`.
- [ ] **BUG-003 — Omnibox:** Gõ `lo`, Chrome gợi ý `localhost:8081`, nhấn **Enter trực tiếp** phải có hành vi điều hướng đúng; không dùng ArrowDown làm cách thay thế trong test.

> Các lỗi Chrome chưa được xác định chắc chắn nguyên nhân. Cần so sánh với IBus, Fcitx5 engine tham chiếu và chế độ tiếng Anh; không mặc định Telexiva tự giải quyết được mọi lỗi của Chrome.

## 8. UX & hiệu năng — P1

- [ ] Độ trễ mỗi phím thấp, không giật/nhấp nháy preedit.
- [ ] Không nhảy con trỏ, không tự thêm khoảng trắng hoặc đổi chữ hoa.
- [ ] Hành vi nhất quán khi gõ nhanh hoặc hệ thống tải cao.
- [ ] Chuyển chế độ nhanh, có phản hồi trạng thái rõ ràng.
- [ ] Tùy chọn ghi nhớ cấu hình theo ứng dụng.
- [ ] Không ghi log nội dung gõ nhạy cảm theo mặc định.

## 9. Kiến trúc engine — P0

- [ ] Lưu **raw keystrokes** cho composition hiện tại.
- [ ] Tách **Telex parser**, **syllable validator**, **Unicode renderer**.
- [ ] Định nghĩa thứ tự ưu tiên của transformation rules.
- [ ] Có replay sự kiện phím để tái hiện bug.
- [ ] Core test được độc lập với Fcitx5.
- [ ] Không sửa văn bản đã commit khi không có cơ chế đồng bộ an toàn.
- [ ] Cùng chuỗi sự kiện + cấu hình phải cho kết quả xác định.
- [ ] Đánh giá kiến trúc MVP trước khi refactor; tránh viết lại không cần thiết.

## 10. Testing & chất lượng — P0

- [ ] Unit tests cho Telex, VNI, Unicode và vị trí đặt dấu.
- [ ] Test nhiều chuỗi phím cho cùng một âm tiết.
- [ ] Test chữ hoa/thường, dấu lặp, gõ sai và sửa lại.
- [ ] Test Backspace/Undo/Reset/focus change.
- [ ] Test số, tiếng Anh, URL, email và code.
- [ ] Integration tests cho preedit/commit và input context.
- [ ] Property-based/fuzz tests cho chuỗi phím ngẫu nhiên.
- [ ] Regression suite cho từng bug được báo cáo.
- [ ] Compatibility matrix theo app/toolkit/session.
- [ ] Chạy test tự động trong CI trước khi release.

## 11. Test case khởi đầu

| Chuỗi phím | Kết quả mong đợi | Nhóm |
|---|---|---|
| `tieengs` | `tiếng` | Telex, dấu cuối |
| `tieesng` | `tiếng` | Telex, dấu giữa |
| `dd` | `đ` | Phụ âm |
| `aw` | `ă` | Nguyên âm |
| `as` | `á` | Dấu sắc |
| `af` | `à` | Dấu huyền |
| `ax` | `ã` | Dấu ngã |
| `API` | `API` | Giữ nguyên viết tắt |
| `1200000` | `1200000` | Nhập số |

> Các chuỗi gõ đặc biệt cần được định nghĩa thành chính sách rõ ràng theo chế độ Telex/VNI và cấu hình; bảng trên là bộ test khởi đầu, không phải đặc tả đầy đủ.

## 12. Lộ trình triển khai đề xuất

1. **Đợt 1 — Observability & Replay:** lưu raw keystrokes, state machine, tái hiện lỗi.
2. **Đợt 2 — Correctness:** Telex rules, syllable parser, tone placement, test cases.
3. **Đợt 3 — Editing:** Backspace, Undo, rollback và sửa giữa từ.
4. **Đợt 4 — Integration:** preedit, commit, focus và xử lý input context.
5. **Đợt 5 — Context-aware typing:** tiếng Anh, số, URL, code.
6. **Đợt 6 — Hardening:** regression, fuzz, compatibility, CI và performance.

### Definition of Done cho mỗi lỗi

- [ ] Có bước tái hiện và môi trường cụ thể.
- [ ] Có test thất bại trước khi sửa.
- [ ] Xác định nguyên nhân hoặc ghi rõ giả thuyết chưa kiểm chứng.
- [ ] Sửa xong test mới đạt và test cũ không hồi quy.
- [ ] Kiểm tra trên ít nhất một ứng dụng thực tế liên quan.
- [ ] Ghi nhận giới hạn còn lại trong release notes.

---

**Ưu tiên đầu tiên:** xây dựng **raw keystroke replay + regression tests**, sau đó mới chỉnh sâu thuật toán. Đây là cách giảm tình trạng sửa được một trường hợp nhưng làm hỏng trường hợp khác.
