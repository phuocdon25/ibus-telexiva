# Vietnamese Telex Input Method — Test Cases

> Tài liệu kiểm thử dành cho IBus, Fcitx5 và engine Telex tùy chỉnh. Phiên bản 1.0 — 2026-11-10.

## 1. Phạm vi và quy ước

- `Strict`: kết quả kỳ vọng theo quy tắc Telex phổ biến khi engine ở chế độ tiếng Việt, không bật kiểm tra chính tả ngăn nhập.
- `Config`: phụ thuộc cấu hình engine (vị trí dấu, kiểm tra chính tả, xử lý phím lặp, bỏ dấu, hoàn nguyên).
- `Regression`: kiểm tra lỗi ứng dụng hoặc môi trường.
- Mỗi case cần ghi: input, output trong lúc composition, output sau commit bằng Space/Enter, trạng thái pass/fail, phiên bản engine, ứng dụng, Wayland/XWayland.
- **Không mặc định** mọi hoán vị phím đều hợp lệ. Các biến thể dấu nhập giữa từ phải kiểm tra thực tế.

## 2. Bảng phím Telex

| Nhóm | Phím | Kết quả | Ví dụ |
|---|---|---|---|
| Chữ | aa | â | `aan` → ân |
| Chữ | aw | ă | `awn` → ăn |
| Chữ | ee | ê | `eem` → êm |
| Chữ | oo | ô | `oom` → ôm |
| Chữ | ow | ơ | `own` → ơn |
| Chữ | uw | ư | `uw` → ư |
| Chữ | dd | đ | `ddi` → đi |
| Dấu | s | sắc | `as` → á |
| Dấu | f | huyền | `af` → à |
| Dấu | r | hỏi | `ar` → ả |
| Dấu | x | ngã | `ax` → ã |
| Dấu | j | nặng | `aj` → ạ |
| Dấu | z | xóa dấu / hoàn nguyên | Phụ thuộc engine |

## 3. Test chữ cái và chữ hoa

| ID | Input | Expected | Loại |
|---|---|---|---|
| CH-01 | `aa` | â | Strict |
| CH-02 | `aw` | ă | Strict |
| CH-03 | `ee` | ê | Strict |
| CH-04 | `oo` | ô | Strict |
| CH-05 | `ow` | ơ | Strict |
| CH-06 | `uw` | ư | Strict |
| CH-07 | `dd` | đ | Strict |
| CH-08 | `AA` | Â | Strict |
| CH-09 | `AW` | Ă | Strict |
| CH-10 | `EE` | Ê | Strict |
| CH-11 | `OO` | Ô | Strict |
| CH-12 | `OW` | Ơ | Strict |
| CH-13 | `UW` | Ư | Strict |
| CH-14 | `DD` | Đ | Strict |
| CH-15 | `Aa` | Â/â theo cấu hình | Config |
| CH-16 | `Dd` | Đ/đ theo cấu hình | Config |

## 4. Ma trận đầy đủ nguyên âm + thanh điệu

| Nguyên âm | Không dấu | s | f | r | x | j |
|---|---|---|---|---|---|---|
| a | a | á | à | ả | ã | ạ |
| aw | ă | ắ | ằ | ẳ | ẵ | ặ |
| aa | â | ấ | ầ | ẩ | ẫ | ậ |
| e | e | é | è | ẻ | ẽ | ẹ |
| ee | ê | ế | ề | ể | ễ | ệ |
| i | i | í | ì | ỉ | ĩ | ị |
| o | o | ó | ò | ỏ | õ | ọ |
| oo | ô | ố | ồ | ổ | ỗ | ộ |
| ow | ơ | ớ | ờ | ở | ỡ | ợ |
| u | u | ú | ù | ủ | ũ | ụ |
| uw | ư | ứ | ừ | ử | ữ | ự |
| y | y | ý | ỳ | ỷ | ỹ | ỵ |

**Cách sinh case:** Với mỗi dòng, lấy chuỗi đầu vào ở cột nguyên âm, nối lần lượt `s/f/r/x/j`, đối chiếu 5 kết quả tương ứng. Tổng: 12 × 6 = 72 trường hợp (kể cả không dấu).

## 5. Một từ — nhiều chuỗi phím

> Nhóm này kiểm tra khả năng nhận dấu nhập ở các vị trí khác nhau. Cột biến thể được đánh dấu `Config` vì engine có thể áp dụng kiểm tra chính tả hoặc chỉ chấp nhận một số thứ tự phím.

| ID | Từ | Chuỗi chuẩn | Biến thể cần thử | Loại biến thể |
|---|---|---|---|---|
| MP-01 | tiếng | `tieengs` | `tieesng`, `tieseng` | Config |
| MP-02 | Việt | `Vieetj` | `Vieejt`, `Viej et` (âm cách: negative) | Config/Negative |
| MP-03 | người | `nguwowif` | `nguwowfi`, `nguwfowi` | Config |
| MP-04 | đường | `dduwowngf` | `dduwowfng`, `dduwfowng` | Config |
| MP-05 | trường | `truwowngf` | `truwowfng`, `truwfowng` | Config |
| MP-06 | thắng | `thawngs` | `thawsng`, `thaswng` | Config |
| MP-07 | thành | `thanhf` | `thafnh` | Config |
| MP-08 | chuyện | `chuyeenj` | `chuyeejn`, `chuyjeen` | Config |
| MP-09 | hướng | `huwowngs` | `huwowsng` | Config |
| MP-10 | Nguyễn | `Nguyeenx` | `Nguyeexn` | Config |
| MP-11 | phước | `phuwowcs` | `phuwowsc` | Config |
| MP-12 | quốc | `quoocs` | `quoosc` | Config |
| MP-13 | hoàng | `hoangf` | `hoafng` | Config |
| MP-14 | khỏe | `khoer` | `kho re` (âm cách: negative) | Config/Negative |
| MP-15 | biết | `bieets` | `bieest` | Config |
| MP-16 | thuyền | `thuyeenf` | `thuyeefn` | Config |
| MP-17 | muộn | `muoonj` | `muoojn` | Config |
| MP-18 | cười | `cuwowif` | `cuwowfi` | Config |
| MP-19 | khuấy | `khuaays` | `khuaasy` | Config |
| MP-20 | quyền | `quyeenf` | `quyeefn` | Config |

**Cần xác minh từng biến thể** thay vì ép kết quả mong đợi giống nhau. Ví dụ các tổ hợp `uwow`, `uow`, `uwo` và thứ tự gõ `w` có thể được engine xử lý khác nhau.

## 6. Vị trí dấu và chính tả

| ID | Input | Expected | Cấu hình |
|---|---|---|---|
| TP-01 | `hoaf` | hòa | Dấu kiểu mới |
| TP-02 | `hoaf` | hoà | Dấu kiểu cũ |
| TP-03 | `thuyr` | thủy | Dấu kiểu mới |
| TP-04 | `thuyr` | thuỷ | Dấu kiểu cũ |
| TP-05 | `quas` | quá | Quy tắc qu |
| TP-06 | `gias` | giá | Quy tắc gi |
| TP-07 | `gif` | gì | Quy tắc gi |
| TP-08 | `yeeus` | yếu | Dấu trên ê |
| TP-09 | `bieets` | biết | Dấu trên ê |
| TP-10 | `muoonj` | muộn | Dấu trên ô |

## 7. Thay đổi, xóa và hoàn nguyên dấu

| ID | Chuỗi thao tác | Kỳ vọng | Loại |
|---|---|---|---|
| CT-01 | `as` rồi `f` | Thay sắc bằng huyền nếu engine hỗ trợ | Config |
| CT-02 | `as` rồi `r` | Thay sắc bằng hỏi nếu hỗ trợ | Config |
| CT-03 | `as` rồi `x` | Thay sắc bằng ngã nếu hỗ trợ | Config |
| CT-04 | `as` rồi `j` | Thay sắc bằng nặng nếu hỗ trợ | Config |
| CT-05 | `as` rồi `z` | Xóa dấu thanh hoặc hoàn nguyên theo cấu hình | Config |
| CT-06 | `aws` rồi `z` | Xác minh dấu nào bị xóa | Config |
| CT-07 | `aa` rồi `z` | Xác minh hoàn nguyên â | Config |
| CT-08 | `dd` rồi `z` | Xác minh hoàn nguyên đ | Config |
| CT-09 | `ass` | Không mất dữ liệu; xác minh quy tắc phím lặp | Config |
| CT-10 | `aaw` | Xác minh ưu tiên quy tắc aa/aw | Config |

## 8. Backspace, cursor, commit, clipboard

| ID | Thao tác | Kỳ vọng |
|---|---|---|
| ED-01 | Nhập `as`, Backspace | Xóa đúng đơn vị theo quy tắc engine |
| ED-02 | Nhập `aas`, Backspace | Không tạo Unicode lỗi |
| ED-03 | Nhập `tieengs`, Left | Con trỏ di chuyển đúng |
| ED-04 | Nhập `tieengs`, Home | Con trỏ về đầu |
| ED-05 | Ctrl+A | Chọn đúng toàn bộ |
| ED-06 | Ctrl+C / Ctrl+V | Giữ nguyên tiếng Việt |
| ED-07 | Ctrl+Z / Ctrl+Y | Undo/redo không hỏng composition |
| ED-08 | `tieengs` + Space | Commit `tiếng ` |
| ED-09 | `tieengs` + Enter | Commit `tiếng` trước xuống dòng |
| ED-10 | Click ngoài input | Không mất chữ hoặc dấu |
| ED-11 | Chọn autocomplete | Không lặp ký tự đầu/cuối |
| ED-12 | Chuyển VN/EN giữa từ | Không mất composition |
| ED-13 | Chọn một phần từ và thay thế | Không thay đổi phần không chọn |
| ED-14 | Paste Unicode NFC và NFD | Hiển thị tương đương, không hỏng dấu |

## 9. Số, tiếng Anh, lập trình, URL

| ID | Input | Kỳ vọng |
|---|---|---|
| RG-01 | `1200000` | Giữ nguyên |
| RG-02 | `1000000000` | Giữ nguyên |
| RG-03 | `1,200,000` | Giữ nguyên |
| RG-04 | `1.200.000` | Giữ nguyên |
| RG-05 | `localhost:8081` | Không biến đổi ngoài ý muốn |
| RG-06 | `http://localhost:8081/` | Không biến đổi |
| RG-07 | `const userName = "test";` | Giữ nguyên khi ở EN/code mode |
| RG-08 | `npm run dev` | Giữ nguyên khi ở EN/code mode |
| RG-09 | `git commit -m "fix"` | Giữ nguyên khi ở EN/code mode |
| RG-10 | Chọn suggestion `Quên chấm công` | Không thêm `Q` |
| RG-11 | Chrome autocomplete | Không lặp hoặc mất ký tự |
| RG-12 | VS Code terminal | Không rơi phím |
| RG-13 | Gõ nhanh 100 ký tự | Không lặp/mất ký tự |
| RG-14 | Nhập email `test@example.com` | Không biến đổi |
| RG-15 | Nhập `foo_bar-baz` | Không biến đổi khi EN/code mode |
| RG-16 | Gõ `lo`, chọn gợi ý localhost bằng Enter | Điều hướng đúng gợi ý được chọn |
| RG-17 | Gõ `lo`, dùng ArrowDown + Enter | Điều hướng đúng gợi ý được chọn |

## 10. Ma trận môi trường

Chạy mỗi case đại diện trong các môi trường:

| Môi trường | Ứng dụng/Widget | Bắt buộc |
|---|---|---|
| GNOME Wayland | GTK Entry / TextView | Có |
| GNOME Wayland | Qt LineEdit / TextEdit | Có |
| GNOME Wayland | Chrome address bar | Có |
| GNOME Wayland | Chrome input / textarea / contenteditable | Có |
| GNOME Wayland | VS Code editor | Có |
| GNOME Wayland | VS Code integrated terminal | Có |
| GNOME Wayland | GNOME Terminal / Ptyxis | Có |
| XWayland | Ứng dụng X11 | Nên có |
| X11 session | GTK/Qt/Chrome | Tùy chọn |

## 11. Mẫu bug report

```yaml
id: RG-10
engine: ibus-or-fcitx5
engine_version: unknown
os: Ubuntu
session: wayland
desktop: GNOME
app: Google Chrome
app_version: unknown
input: "Quên chấm công"
action: "Select autocomplete suggestion"
expected: "Quên chấm công"
actual: "Quên chấm côngQ"
reproducibility: "not measured"
severity: medium
status: open
```

## 12. Tiêu chí pass/fail

1. `Strict`: kết quả đúng với chế độ Telex đã khai báo.
2. `Config`: chỉ đánh giá sau khi ghi rõ thiết lập engine và kết quả mong muốn.
3. `Negative`: input có khoảng trắng hoặc chuỗi không hợp lệ không được âm thầm biến thành một từ khác.
4. `Regression`: tái hiện lỗi trước khi sửa, sau đó kiểm tra không tái phát.
5. Mỗi lỗi cần lưu cả sự kiện phím, trạng thái composition, văn bản đã commit và ứng dụng đang chạy.

## 13. Hướng mở rộng corpus

- Sinh ma trận toàn bộ nguyên âm × 6 thanh điệu × chữ hoa/chữ thường.
- Dùng từ điển tiếng Việt có giấy phép phù hợp để tạo corpus từ đơn và âm tiết.
- Sinh biến thể vị trí phím dấu: ngay sau nguyên âm, giữa âm tiết, cuối âm tiết; **đánh dấu là candidate** trước khi xác minh.
- Tạo cặp test theo cấu hình bật/tắt kiểm tra chính tả, vị trí dấu kiểu cũ/mới, tự động sửa lỗi.
- Lưu test fixtures JSON/CSV và kết quả chạy theo phiên bản engine để theo dõi regression.
- Bổ sung test Unicode grapheme, normalization, tốc độ gõ, IME preedit/commit và chuyển focus.

