# Baseline: `ibus-unikey` trên Chrome Wayland

| | |
|---|---|
| Ngày | 2026-11-10 |
| Môi trường | Ubuntu 26.04, GNOME Wayland, Chrome 148 (native Wayland), IBus 1.5.34, `ibus-unikey 0.7.0~beta1`, Telex |
| Công cụ | `tools/playground/index.html` (bản trước commit sửa thời điểm đọc value) |
| Log gốc | 1138 sự kiện; giữ local trong `docs/findings/logs/` (không đưa lên repo vì chứa nội dung gõ thử) |

## Kết luận chính

`ibus-unikey` giữ **mọi ký tự của một "từ" trong preedit** (composition), kể cả chữ không có dấu, chữ số, dấu `:` và dấu cách ở cuối. Composition chỉ kết thúc ở dấu cách hoặc dấu câu. Đây là nguyên nhân trực tiếp của BUG-001, BUG-002 và BUG-004, và là nguyên nhân rất có thể của BUG-003.

## Bằng chứng theo từng lỗi

### BUG-004 — Từ chưa hoàn thiện cho tới khi nhấn Space: **tái hiện được**

Gõ `vieejt␣` ở ô văn bản:

```
compositionstart
compositionupdate "v" → "vi" → "vie" → "viê" → "việ" → "việt" → "việt␣"
compositionend   "việt␣"
```

Cả dấu cách cũng nằm trong composition; chữ chỉ thật sự thuộc về ô sau `compositionend`.

### BUG-001 — Số bị lặp trong ô tiền tệ: **tái hiện được**

Ở chế độ English (lượt đầu, `insertText` từng chữ số), ô tiền tệ cho kết quả đúng.

Ở chế độ tiếng Việt, gõ `12000000`:

```
compositionupdate "1" → "12" → "120" → "1200"     value: 1200
                                                  (trang định dạng thành "1,200" → Chrome hủy composition)
compositionstart  (mới, tại vị trí con trỏ)
compositionupdate "12000"                         value: 1,200 + "12000" = 1,20012000
compositionstart  (mới)
compositionupdate "120000"                        value: 120,012,000 + "120000" …
…
change            12,001,200,012,000,012,000,001,200,000,012,000,000
```

Cơ chế:
1. Unikey giữ chữ số trong preedit.
2. Trang gán lại `value` để chèn dấu phẩy, làm Chrome kết thúc composition hiện tại, giữ nguyên phần đã hiển thị.
3. Unikey **không biết** composition đã bị hủy; bộ đệm của nó vẫn là `1200`, gõ thêm `0` thì nó gửi preedit `12000` và Chrome chèn **nguyên chuỗi** vào vị trí con trỏ.
4. Mỗi phím tiếp theo lặp lại bước 2–3, nên các chữ số bị nhân lên.

### BUG-002 — Chọn gợi ý bị dư ký tự: **tái hiện được**

Ô `<datalist>`, gõ `Q` rồi chọn "Quên chấm công":

```
compositionupdate "Q"                  value: Q   (chưa commit)
keydown (chọn gợi ý)
input                                  value: Quên chấm công
change
beforeinput insertText "Q"             ← Unikey commit preedit còn treo khi ô mất focus
input                                  value: Quên chấm côngQ
```

Cơ chế: chữ `Q` vẫn ở preedit khi trình duyệt thay toàn bộ giá trị. Khi ô kết thúc composition (blur/reset), IBus commit phần preedit còn lại vào sau giá trị mới.

### BUG-003 — Omnibox: **gián tiếp**

Ở ô tìm kiếm mô phỏng, cả chuỗi `localhost` nằm trong một composition duy nhất. Ô mô phỏng (giống Chrome) không tự điền inline khi đang composition, nên người dùng phải gõ hết. Điều này khớp với giả thuyết: khi có preedit, Chrome không đưa ra inline autocomplete, nên Enter tìm kiếm thay vì điều hướng. Cần xác nhận trên omnibox thật.

### Autocomplete lịch sử của Chrome: **chưa đủ dữ liệu**

Sau khi bấm Lưu, gợi ý không hiện cho tới khi tải lại trang. Lần thử với tiếng Việt, người dùng đã gõ hết `Quên chấm công` thay vì chọn gợi ý. Cần thử lại sau F5, so sánh English và tiếng Việt: popup gợi ý có hiện khi `Q` đang ở preedit hay không (nghi ngờ: popup autofill cũng bị chặn khi đang composition).

## Quan sát phụ

- **Không có `keydown` cho phím do IME xử lý.** Khi Unikey đang soạn, Chrome trên Wayland không phát `keydown` cho các phím chữ (chỉ còn `Shift`, `Backspace`, `Enter`). Web app nghe `keydown` (phím tắt, Enter để submit, React `onKeyDown`) sẽ hành xử khác so với English. Pass-through first trả lại `keydown` bình thường cho các phím không biến đổi.
- Backspace sau khi composition đã kết thúc đi thẳng tới ứng dụng (`deleteContentBackward`), không qua Unikey.
- Ô mật khẩu: không có composition. Engine hoặc Chrome đã tắt IME đúng cho ô password (FR-011 hoạt động với Unikey).

## Hệ quả cho thiết kế

1. Xác nhận FR-009 "pass-through first": chữ số, chữ cái không biến đổi và dấu cách **không được** nằm trong preedit.
2. Xác nhận nhu cầu của surrounding text guard: trang có thể thay đổi nội dung ô bất cứ lúc nào (định dạng số, chọn gợi ý); engine phải phát hiện và reset bộ đệm, không được tiếp tục dựa trên bộ đệm cũ.
3. Thêm vào test plan: kiểm tra `keydown` có được phát cho phím không biến đổi.

## Việc tiếp theo

- [ ] Thử lại autocomplete lịch sử sau F5 (English và tiếng Việt).
- [ ] Thử BUG-003 trên omnibox thật, ghi lại có hiện inline suggestion khi đang gõ tiếng Việt không.
- [ ] Chạy lại với playground đã sửa để có cột value chính xác cho ô tiền tệ.
