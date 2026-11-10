# Telexiva

**Vietnamese Input Method for Linux**  
**Project Specification & Technical Design Document**

| Thông tin | Giá trị |
|---|---|
| Project | Telexiva |
| Version | 0.3.0 (Planning — sau review lần 2) |
| Platform | Ubuntu 26.04 LTS |
| Primary Desktop | GNOME / Wayland |
| Programming Language | C++20 (core + engine); Python cho prototype Phase 0 |
| Input Method Framework | **IBus** (engine), xem §6.0 |
| GUI Framework | Settings app: GTK4/libadwaita hoặc Qt6 (chốt ở Phase 4) |
| Build System | CMake + Ninja |
| Project Type | Open Source |
| License | Đề xuất GPL-3.0-or-later (cần chốt, xem §15) |
| Status | Planning |

### Lịch sử thay đổi

| Version | Thay đổi chính |
|---|---|
| 0.1.0 | Bản đầu tiên. |
| 0.2.0 | Thêm FR-009 Commit Strategy, FR-010 Per-app profile, FR-011 Password field; đặc tả Telex theo UniKey Windows; NFR có số đo; môi trường tái hiện lỗi; bỏ `telexivactl`; VNI dời khỏi MVP. |
| 0.3.0 | **Chốt IBus engine** thay cho Fcitx5 (§6.0). Xác nhận nguyên nhân nghi ngờ của các lỗi là preedit. Đổi FR-009 thành nguyên tắc **"pass-through first"** kèm kiểm tra surrounding text. Thêm prototype Python vào Phase 0. Phụ lục A đổi thành quy trình chạy song song với `ibus-unikey`. |

---

## 1. Tổng quan dự án

### 1.1. Giới thiệu

**Telexiva** là bộ gõ tiếng Việt cho Linux, chạy dưới dạng **IBus engine** trên Ubuntu GNOME/Wayland. Mục tiêu là trải nghiệm gõ **giống UniKey trên Windows nhất có thể**: không gạch chân, chữ xuất hiện ngay, không ký tự dư. Ưu tiên ổn định trong trình duyệt và VS Code, nơi người dùng chính làm việc hằng ngày với vai trò web developer.

Kiến trúc gồm một **core độc lập** (quy tắc tiếng Việt, state machine) và một **frontend IBus**. Core không phụ thuộc IBus, nên sau này có thể viết thêm frontend Fcitx5 cho các desktop khác.

### 1.2. Lý do phát triển

Môi trường hiện tại của người dùng chính:

| Thành phần | Phiên bản / trạng thái |
|---|---|
| OS | Ubuntu 26.04 LTS, GNOME, Wayland |
| Bộ gõ | IBus 1.5.34 + `ibus-unikey 0.7.0~beta1` |
| Chrome | 148, chạy **native Wayland** (`--ozone-platform=wayland`), không có flag IME |
| VS Code | 1.120 |
| im-config | Chế độ auto (chưa có `~/.xinputrc`), đang chọn IBus |

Các lỗi đã ghi nhận (chi tiết tái hiện ở §8.3):

- Nhập số trong một số ô tiền tệ trên website bị lặp hoặc sai thứ tự.
- Chọn gợi ý autocomplete trên Chrome bị dư ký tự.
- Nhấn Enter khi Chrome gợi ý URL trên thanh địa chỉ lại tìm kiếm thay vì điều hướng.
- Ở nhiều nơi (đặc biệt là terminal), từ đang gõ ở trạng thái "chưa hoàn thiện" và chỉ được đưa vào thật khi nhấn Space.

**Phân tích nguyên nhân (giả thuyết mạnh, cần kiểm chứng ở Phase 0):**

`ibus-unikey` giữ từ đang gõ ở dạng **preedit** (vùng chữ tạm, chưa thuộc về ứng dụng) cho tới khi kết thúc từ. Người dùng đã xác nhận triệu chứng này. Điểm chung của ba lỗi Chrome là chuỗi gõ **không cần biến đổi tiếng Việt** (`1200000`, `Q`, `lo`), và ở chế độ English thì không lỗi. Do đó:

| Lỗi | Cơ chế nghi ngờ |
|---|---|
| BUG-001 | Số bị giữ trong preedit hoặc bị sửa lại trong khi JavaScript của trang định dạng lại ô (`1,200,000`) |
| BUG-002 | Chọn gợi ý làm ô mất trạng thái soạn, IBus commit preedit `Q` vào sau phần gợi ý |
| BUG-003 | Chrome không hiện inline autocomplete khi đang có preedit; Enter làm commit `lo` rồi mới tới Enter, nên Chrome tìm kiếm `lo` |

Nếu engine **cư xử y hệt English khi không cần biến đổi** (FR-009), cả ba lỗi có khả năng cao không còn xảy ra.

Danh sách lỗi có thể chưa đầy đủ. Mọi lỗi phát hiện thêm được ghi vào `docs/known-issues.md` theo mẫu ở §12.3.

### 1.3. Tầm nhìn

Bộ gõ tiếng Việt native, nhẹ, ổn định, cho cảm giác gõ như UniKey Windows; kiến trúc rõ ràng, dễ đóng góp, có thể mở rộng sang framework và bản phân phối khác.

### 1.4. Khác biệt so với các bộ gõ hiện có

| Bộ gõ | Tình trạng |
|---|---|
| `ibus-unikey` | Bản beta cũ, dùng preedit, gây các lỗi ở §1.2 |
| `ibus-bamboo` | README ghi đã đình trệ, có thể không được duy trì |
| `fcitx5-unikey`, `fcitx5-bamboo` | Còn phát triển, nhưng Fcitx5 tích hợp kém với GNOME Wayland (§6.0) |

Telexiva tồn tại vì hai lý do, theo thứ tự ưu tiên:

1. **Học tập:** môi trường học C++20 và hệ thống nhập liệu Linux một cách bài bản (§2.2). Người dùng không cần dùng sớm vì IBus hiện tại vẫn dùng tạm được.
2. **Chất lượng:** một IBus engine còn được duy trì cho GNOME, gõ không preedit kiểu UniKey Windows, có kiểm tra surrounding text để tránh ký tự dư, và có bộ regression test tái hiện được cho các lỗi trình duyệt.

## 2. Mục tiêu dự án

### 2.1. Mục tiêu chính

1. Engine Telex có hành vi tương đương UniKey Windows (FR-001).
2. IBus engine chạy trên GNOME Wayland, song song được với các engine khác.
3. Chuyển đổi tiếng Việt / tiếng Anh.
4. Quản lý trạng thái riêng theo input context.
5. Commit strategy "pass-through first" và cấu hình theo ứng dụng (FR-009, FR-010).
6. Unit test, integration test và regression test cho các lỗi trình duyệt.
7. Đóng gói `.deb` cho Ubuntu.

### 2.2. Mục tiêu học tập

- C++20 và kiến trúc ứng dụng native Linux.
- Event-driven programming; Unicode và UTF-8.
- IBus engine API, GObject (viết wrapper RAII bằng C++), D-Bus, Wayland `text-input-v3`, cách Mutter chuyển input tới IBus.
- CMake, unit testing, debugging và đóng gói phần mềm.

Vì người dùng ưu tiên học sâu hơn dùng sớm, dự án **giữ đủ các phase**. Tiến độ không bị ép, nhưng mỗi phase phải có deliverable kiểm chứng được.

### 2.3. Ngoài phạm vi phiên bản đầu

- Windows/macOS, cloud sync, AI autocomplete, sửa chính tả bằng mô hình ngôn ngữ, bàn phím ảo.
- Frontend Fcitx5 (để dành cho sau, core đã sẵn sàng).
- **VNI** (dời sang sau MVP, xem FR-002).
- **Gõ tắt / macro** kiểu UniKey (dời sang sau MVP, xem FR-012).
- Bảng mã khác Unicode (TCVN3, VNI-Windows…). Telexiva chỉ xuất Unicode dựng sẵn (NFC).
- CLI riêng. Dùng công cụ sẵn có (`ibus engine`, `gsettings`, D-Bus).

## 3. Đối tượng sử dụng

- **Người dùng chính (persona ưu tiên): web developer.** Làm việc chủ yếu trong Chrome (form, autocomplete, omnibox, ô nhập số) và VS Code (code, comment, commit message, terminal tích hợp). Thường xuyên xen kẽ tiếng Việt và tiếng Anh/code trong cùng một đoạn.
- **Người dùng phổ thông:** nhập tiếng Việt trên Ubuntu trong trình duyệt, văn phòng, ứng dụng desktop.
- **Cộng đồng mã nguồn mở:** tìm hiểu, cải tiến và đóng góp.

## 4. Yêu cầu chức năng

Mức ưu tiên: **P0** bắt buộc cho MVP · **P1** nên có trong MVP · **P2** sau MVP.

### FR-001: Telex theo hành vi UniKey Windows — P0

**Nguyên tắc:** khi có điểm mơ hồ, hành vi đúng là hành vi của **UniKey 4.x trên Windows với cấu hình mặc định**. Mọi khác biệt có chủ đích phải ghi vào `docs/telex-spec.md`.

#### a) Biến đổi ký tự

| Phím | Kết quả | Ví dụ |
|---|---|---|
| `aa` `ee` `oo` | â ê ô | `aan` → `ân` |
| `aw` `ow` `uw` | ă ơ ư | `awn` → `ăn` |
| `dd` | đ | `ddi` → `đi` |
| `w` đứng riêng | ư | `w` → `ư`, `tw` → `tư` |
| `[` `]` | ơ ư | `t[` → `tơ` |
| `{` `}` | Ơ Ư | |
| `uow`, `uwow` | ươ | `nguoiwf` → `người`, `duowcj` → `được` |

Dấu `w` áp dụng cho cả cụm nguyên âm khi hợp lệ: `uo` + `w` → `ươ`, `oa` + `w` → `oă` (`hoawcj` → `hoặc`).

#### b) Dấu thanh

| Phím | Dấu | Ví dụ |
|---|---|---|
| `s` | Sắc | `as` → `á` |
| `f` | Huyền | `af` → `à` |
| `r` | Hỏi | `ar` → `ả` |
| `x` | Ngã | `ax` → `ã` |
| `j` | Nặng | `aj` → `ạ` |
| `z` | Xóa dấu thanh (giữ dấu mũ/móc) | `áz` → `a`, `ấz` → `â` |

- **Gõ dấu tự do (bật mặc định):** phím dấu có thể đặt ở bất kỳ vị trí nào sau nguyên âm trong từ. `tieengs`, `tiesng`, `tieesng` đều ra `tiếng`. `nguoiwf` và `nguwowif` đều ra `người`.
- **Đổi dấu:** gõ phím dấu khác thì thay dấu cũ. `asf` → `à`.

#### c) Hủy biến đổi bằng cách gõ lặp phím

| Chuỗi phím | Kết quả |
|---|---|
| `ass` | `as` |
| `aaa` | `aa` |
| `aww` | `aw` |
| `ww` | `w` |
| `ddd` | `dd` |
| `[[` | `[` |

Sau khi đã hủy, phím đó không còn kích hoạt biến đổi nữa trong từ hiện tại (giống UniKey).

#### d) Vị trí đặt dấu thanh

- **Mặc định: kiểu cũ**, như UniKey mặc định: `hòa`, `thúy`, `khỏe`.
- Tùy chọn **kiểu mới**: `hoà`, `thuý`, `khoẻ`.
- Quy tắc đặt dấu phải xử lý đúng: `qu`/`gi` (`quý`, `giả`), `ươ` (`được`), `uyê` (`khuyến`), nguyên âm có mũ/móc ưu tiên nhận dấu.

#### e) Kiểm tra chính tả và tự khôi phục (bật mặc định)

Tương đương tùy chọn "Bật kiểm tra chính tả" + "Tự động khôi phục phím với từ sai" của UniKey:

- Khi chuỗi phím không tạo thành âm tiết tiếng Việt hợp lệ, engine **ngừng biến đổi** và khi kết thúc từ (space, dấu câu, Enter) thì **khôi phục nguyên chuỗi phím gốc**.
- Ví dụ bắt buộc phải qua test (rất quan trọng với developer):

| Gõ | Kết quả mong đợi | Lý do |
|---|---|---|
| `text` | `text` | Âm cuối `t` không đi với dấu ngã |
| `class` | `class` | `cl` không phải phụ âm đầu hợp lệ |
| `for` | `for` | Âm cuối `r` không hợp lệ (phải khôi phục `r` thay vì dấu hỏi) |
| `function` | `function` | Không hợp lệ |
| `const` | `const` | Không hợp lệ |
| `width` | `width` | Không hợp lệ |
| `viet` + `j` | `việt` | Hợp lệ |

- Danh sách ngoại lệ: các từ tiếng Anh *trùng với âm tiết tiếng Việt hợp lệ* (`as`, `is`, `of`, `if`…) **không** tự khôi phục. Đây là hạn chế đã biết, giống UniKey; người dùng gõ lặp phím (`ass`) hoặc chuyển sang English. Xem xét whitelist từ tiếng Anh ở P2.

#### f) Chữ hoa

- Giữ nguyên chữ hoa/thường theo từng ký tự: `Vieejt` → `Việt`, `VIEEJT` → `VIỆT`, `DDAAY` → `ĐÂY`.
- Phím dấu viết hoa có tác dụng như viết thường: `AS` → `Á`.
- Caps Lock xử lý như Shift với chữ cái.

#### g) Kết thúc từ

Từ đang soạn kết thúc khi gặp: space, Enter, Tab, dấu câu, số (trong Telex), phím điều hướng (mũi tên, Home, End, PageUp/Down), click chuột hoặc đổi focus.

### FR-002: VNI — P2

Phím 1–5 cho dấu thanh, 6–9 biến đổi nguyên âm/phụ âm, 0 xóa dấu. Dời sang sau MVP vì người dùng chính chỉ gõ Telex. Khi làm cần kiểm thử kỹ việc nhập số, liên quan trực tiếp BUG-001.

### FR-003: Chế độ tiếng Anh — P0

Khi ở English, mọi phím đi thẳng tới ứng dụng (engine trả `FALSE` cho mọi key event), engine không giữ trạng thái. Hành vi phải giống hệt khi không có bộ gõ.

### FR-004: Chuyển đổi chế độ — P0

Có hai tầng chuyển đổi, cần phân biệt rõ:

- **Giữa các input source của GNOME** (ví dụ Telexiva ↔ bàn phím English ↔ Unikey): do GNOME quản lý bằng `Super+Space`. Telexiva không can thiệp.
- **Bên trong Telexiva, giữa Vietnamese và English** (giống UniKey): engine tự xử lý.
  - Mặc định **`Ctrl+Shift`** (nhấn rồi thả, không kèm phím khác). Tùy chọn khác: `Alt+Z`.
  - Chỉ kích hoạt khi `Ctrl+Shift` được nhấn và thả **mà không có phím nào khác xen giữa**, để không xung đột với các tổ hợp `Ctrl+Shift+<phím>` của VS Code.
  - Hiển thị trạng thái V/E trên indicator input source ở top bar của GNOME (qua IBus property). Cần kiểm chứng cơ chế hiển thị ở Phase 0.

### FR-005: Composition — P0

Nhận sự kiện phím, cập nhật từ đang soạn, commit, backspace, reset, focus change, hủy composition. Backspace xóa từng ký tự **đã hiển thị** (giống UniKey): `việt` + Backspace → `việ`, và engine vẫn tiếp tục biến đổi đúng nếu gõ tiếp.

### FR-006: Input context — P0

Mỗi input context có trạng thái composition riêng. Đổi focus giữa hai ô, giữa hai tab, hoặc giữa Chrome và VS Code không làm rò trạng thái.

### FR-007: Settings — P1

App `telexiva-settings` (IBus không tự sinh giao diện cấu hình). Cho phép chọn: kiểu đặt dấu (cũ/mới), bật/tắt kiểm tra chính tả và tự khôi phục, gõ dấu tự do, phím tắt chuyển chế độ, commit strategy mặc định và theo ứng dụng (FR-010), khôi phục cấu hình mặc định, xem phiên bản.

- Cấu hình lưu bằng GSettings hoặc file trong `~/.config/telexiva/`; engine nhận thay đổi mà không cần khởi động lại.
- Toolkit: GTK4/libadwaita (hợp với GNOME) hoặc Qt6. Chốt ở Phase 4.
- Mở được từ menu input source của GNOME (khai báo `setup` trong component XML của IBus).

### FR-008: Playground — P0

Trang HTML local (chạy trong Chrome) mô phỏng các tình huống lỗi: text input, textarea, ô tiền tệ có định dạng lại số (`1,200,000`), `<datalist>` / autocomplete tự viết, ô `type=password`, `contenteditable`. Mỗi ô ghi lại chuỗi sự kiện `keydown` / `beforeinput` / `input` / `compositionstart|update|end` để so sánh giữa các bộ gõ. Playground không thay thế kiểm thử trên trang thật. Ưu tiên P0 vì là công cụ đo của Phase 0.

### FR-009: Commit Strategy — "pass-through first" — P0

Đây là yêu cầu quan trọng nhất để khắc phục các lỗi ở §1.2.

#### Nguyên tắc

1. **Pass-through first.** Phím nào không làm thay đổi chữ đã hiển thị thì trả về cho ứng dụng **như phím thật** (engine trả `FALSE`). Ứng dụng thấy y hệt chế độ English. Áp dụng cho: số, ký tự không phải chữ, và chữ cái không gây biến đổi (ví dụ `l`, `o` trong `lo`; `Q`).
2. **Chỉ can thiệp khi cần.** Khi phím gây biến đổi (ví dụ `lo` + `o` → `lô`), engine xóa phần chữ cũ và đưa chữ mới vào theo strategy của ứng dụng (bảng dưới).
3. **Kiểm tra trước khi sửa (surrounding text guard).** Trước khi xóa, nếu ứng dụng hỗ trợ surrounding text, engine đối chiếu chữ thật trước con trỏ với từ đang soạn. Nếu không khớp (do Chrome vừa điền gợi ý, trang vừa định dạng lại, người dùng click chỗ khác…), engine **reset từ đang soạn và không sửa gì**. Không bao giờ xóa chữ mà engine không chắc là do mình tạo ra.
4. **Không preedit mặc định.** Không có vùng chữ tạm, không gạch chân, chữ thuộc về ứng dụng ngay khi gõ.

#### Các strategy

| Strategy | Cách sửa chữ khi cần biến đổi | Dùng cho | Rủi ro đã biết |
|---|---|---|---|
| **S2 — Surrounding text** (mặc định) | `delete_surrounding_text` rồi `commit_text` | Ứng dụng có hỗ trợ surrounding text (Chrome, GTK, Qt — cần kiểm chứng) | Một số ứng dụng hỗ trợ chưa đúng |
| **S3 — Giả lập Backspace** | `forward_key_event(BackSpace)` × N rồi `commit_text` | Terminal (không có surrounding text) và ứng dụng không hỗ trợ S2 | Thứ tự giữa phím forward và commit trên Wayland cần kiểm chứng; không có guard |
| **S1 — Preedit** (dự phòng) | Từ đang soạn ở dạng preedit, commit khi kết thúc từ | Ứng dụng mà S2 và S3 đều lỗi | Chính là cơ chế gây BUG-002, BUG-003 |

#### Yêu cầu

- MVP hỗ trợ **S2 và S3**; S1 là P1.
- Engine phát hiện ứng dụng không có surrounding text (qua capability của client) và tự chọn S3 hoặc S1 theo app profile.
- Terminal (GNOME Terminal, Ptyxis, terminal tích hợp VS Code) mặc định dùng **S3**, vì terminal không cung cấp surrounding text.
- Mỗi strategy có regression test riêng cho các lỗi ở §8.3.

### FR-010: Cấu hình theo ứng dụng (per-app profile) — P1

Xác định ứng dụng theo thông tin client mà IBus cung cấp (cần kiểm chứng trên Wayland ở Phase 0). Mỗi profile cho phép đặt:

- Commit strategy (FR-009).
- Chế độ mặc định (Vietnamese/English) khi focus vào ứng dụng.
- Ghi nhớ chế độ gần nhất theo ứng dụng (bật/tắt).

Profile mặc định đi kèm: Chrome/Chromium, VS Code, terminal (GNOME Terminal/Ptyxis), Firefox.

### FR-011: Ô mật khẩu — P0

Khi input context có purpose là password hoặc PIN, tự động pass-through như English và **không đưa phím vào core**. Rời ô mật khẩu thì trả về chế độ trước đó.

### FR-012: Gõ tắt (macro) — P2

Tương đương tính năng gõ tắt của UniKey. Ngoài phạm vi MVP.

## 5. Yêu cầu phi chức năng

### NFR-001: Hiệu năng

| Chỉ số | Mục tiêu |
|---|---|
| Thời gian core xử lý một phím | < 0.1 ms (p99), đo bằng benchmark |
| Thời gian engine xử lý một phím (từ nhận event đến commit) | < 2 ms (p99) |
| Bộ nhớ thường trú của engine | < 20 MB |
| Network | Không có bất kỳ kết nối mạng nào |

Không có tác vụ chặn (I/O file, D-Bus đồng bộ) trong luồng xử lý phím.

### NFR-002: Ổn định

- Core không throw exception qua biên engine; mọi lỗi được bắt và reset context về trạng thái an toàn.
- Lỗi của engine không làm treo ứng dụng đang gõ. Trường hợp xấu nhất là mất biến đổi của từ đang soạn, không bao giờ xóa nhầm văn bản đã có (FR-009 guard).
- Fuzz test core với chuỗi phím ngẫu nhiên: không crash, không vòng lặp vô hạn, output luôn là UTF-8 hợp lệ.

### NFR-003: Tương thích

Ma trận kiểm thử bắt buộc (ưu tiên từ trên xuống):

| Ứng dụng | Chế độ hiển thị | Strategy dự kiến | Ưu tiên |
|---|---|---|---|
| Google Chrome | Native Wayland | S2 | P0 |
| VS Code — editor | Mặc định | S2 | P0 |
| VS Code — terminal tích hợp | Mặc định | S3 (cần kiểm chứng) | P0 |
| Terminal (Ptyxis/GNOME Terminal) | Wayland | S3 | P1 |
| Ứng dụng GTK4 (GNOME Text Editor) | Wayland | S2 | P1 |
| Google Chrome | XWayland (`--ozone-platform=x11`) | S2 | P2 |
| Ứng dụng Qt6 | Wayland | S2 | P2 |
| Firefox | Wayland | S2 | P2 |

Lưu ý: editor và terminal tích hợp của VS Code chạy trong cùng một tiến trình. Cần kiểm chứng engine có phân biệt được hai nơi này không (ví dụ qua surrounding text capability). Kết quả ghi trong `docs/compatibility.md`.

### NFR-004: Bảo mật và riêng tư

Không lưu nội dung người dùng nhập; không gửi phím ra mạng; log không bao giờ chứa ký tự người dùng gõ hay surrounding text (chỉ log loại sự kiện, độ dài, mã lỗi); không yêu cầu root khi chạy hằng ngày; ô mật khẩu không đi qua core (FR-011).

### NFR-005: Bảo trì

Core không phụ thuộc IBus; độ phủ test của core ≥ 90% dòng; có coding convention, tài liệu build và contribution; CI chạy unit test cho mỗi commit.

## 6. Kiến trúc hệ thống

### 6.0. Quyết định framework: IBus

Ghi lại trong `docs/adr/0001-framework.md`.

**Bối cảnh.** Trên GNOME/Wayland, Mutter chỉ chuyển input từ giao thức `text-input-v3` sang IBus. Fcitx5 chỉ nhận được phím qua IM module của GTK/Qt mà ứng dụng tự nạp, và cần extension Kimpanel (không có trong kho Ubuntu 26.04) để hiện trạng thái. Nhận định "Fcitx5 hỗ trợ Wayland tốt hơn" đúng với KDE, Sway, Hyprland, nhưng không đúng với GNOME. Nhiều nguồn tham khảo cũng kết luận IBus phù hợp hơn với GNOME Wayland.

**Quyết định.** Telexiva là một IBus engine.

**Hệ quả.**

| Mặt | Hệ quả |
|---|---|
| Tích hợp GNOME | Native: hiện trong Settings → Keyboard → Input Sources, chuyển bằng `Super+Space` |
| Chrome native Wayland | Hoạt động qua đường Mutter → IBus đang dùng |
| Cài đặt song song | Chỉ thêm một engine vào IBus; chạy song song với `ibus-unikey`, rủi ro rất thấp |
| Surrounding text | IBus có API; khả năng hỗ trợ thực tế của từng ứng dụng cần kiểm chứng |
| API | C/GObject; viết wrapper RAII mỏng bằng C++20, giữ core sạch |
| Settings UI | Phải tự viết (FR-007) |
| Desktop khác | Frontend Fcitx5 là hướng mở rộng sau MVP; core đã độc lập |

### 6.1. Sơ đồ

```text
+--------------------------------+
|      Linux Applications        |
|  Chrome / VS Code / GTK / Qt   |
+---------------+----------------+
                | Wayland text-input-v3 (qua Mutter)
                | hoặc GTK/Qt IM module
                v
+--------------------------------+
|          IBus daemon           |
+---------------+----------------+
                | D-Bus
                v
+--------------------------------+
|   ibus-engine-telexiva         |
| IBus adapter (GObject wrapper) |
| Context state / App profile    |
| Commit strategy S1/S2/S3       |
| Surrounding text guard         |
+---------------+----------------+
                | API trung lập: KeyEvent -> EditAction
                v
+--------------------------------+
|        Telexiva Core           |
| Telex rules / Syllable model   |
| Tone placement / Spell check   |
| Composition State Machine      |
+--------------------------------+

+--------------------------------+
|      telexiva-settings         |
| GSettings / config file        |
+--------------------------------+
```

### 6.2. Telexiva Core

Xử lý ký tự, quy tắc Telex, mô hình âm tiết, kiểm tra chính tả, trạng thái soạn thảo và Unicode. Không phụ thuộc GTK, Qt, IBus hay Fcitx5. Với mỗi phím, core trả về một `EditAction` trung lập:

- `PassThrough`: phím không làm đổi chữ, để ứng dụng tự xử lý.
- `Replace{delete_count, text}`: xóa `delete_count` ký tự cuối của từ đang soạn, chèn `text`.
- `Reset`: kết thúc từ, xóa trạng thái.

Core cũng cung cấp "chữ đang hiển thị của từ hiện tại" để engine đối chiếu với surrounding text (FR-009 guard).

### 6.3. IBus engine

Nhận key event, quản lý trạng thái theo input context, áp dụng app profile, ánh xạ `EditAction` sang strategy, chạy guard, xử lý focus/reset/destroy, chuyển chế độ và cập nhật indicator. Đăng ký với IBus qua component XML (`/usr/share/ibus/component/telexiva.xml`).

### 6.4. Settings

Xem FR-007.

## 7. Cấu trúc mã nguồn

```text
telexiva/
├── CMakeLists.txt
├── README.md
├── LICENSE
├── CONTRIBUTING.md
├── prototype/           # prototype Python của Phase 0, không đóng gói
├── src/
│   ├── core/            # engine, telex, syllable, spell, unicode — không phụ thuộc framework
│   ├── ibus/            # ibus-engine-telexiva: adapter, commit strategy, app profile
│   └── settings/        # telexiva-settings
├── tests/
│   ├── core/            # unit test + bảng test dạng dữ liệu (input -> expected)
│   ├── fuzz/
│   ├── integration/
│   └── regression/
├── tools/
│   ├── playground/      # trang HTML (FR-008)
│   └── bench/
├── data/
│   ├── icons/
│   ├── ibus/            # component XML
│   └── config/          # app profile mặc định, GSettings schema
├── packaging/
│   └── debian/
└── docs/
    ├── adr/
    ├── architecture.md
    ├── telex-spec.md
    ├── development.md
    ├── compatibility.md
    ├── known-issues.md
    └── test-plan.md
```

## 8. Chiến lược kiểm thử

### 8.1. Unit Testing

Các ca test Telex viết dạng **bảng dữ liệu** (chuỗi phím → kết quả mong đợi, kèm cấu hình), để dễ bổ sung và đối chiếu với UniKey. Bao phủ: biến đổi ký tự, dấu thanh, gõ dấu tự do, hủy bằng lặp phím, vị trí dấu cũ/mới, kiểm tra chính tả và tự khôi phục, chữ hoa, backspace, reset, chuyển chế độ, chuỗi không hợp lệ, và **chuỗi `EditAction` sinh ra** (đặc biệt: phím không biến đổi phải ra `PassThrough`). Bổ sung fuzz test (NFR-002) và benchmark (NFR-001).

### 8.2. Integration Testing

- Core ↔ IBus adapter: test với IBus engine giả lập / mock client.
- Engine ↔ ứng dụng thật: checklist thủ công trong `docs/test-plan.md` cho từng ô của ma trận NFR-003. Tự động hóa bằng Playwright/Puppeteer với IME thật ở mức P2.

### 8.3. Regression Testing

Mỗi lỗi phải được kiểm tra với: `ibus-unikey` (đối chứng hiện tại), Telexiva ở từng strategy, và chế độ English (đối chứng). Ghi rõ Chrome chạy Wayland hay XWayland.

**BUG-001 — Numeric Input Duplication**

- Môi trường: Chrome 148 Wayland, `ibus-unikey`, chế độ tiếng Việt Telex.
- Trang tái hiện: *cần bổ sung URL thật*, và tái tạo bằng ô tiền tệ trong playground (tự định dạng `1,200,000` khi gõ).
- Bước: focus ô, gõ `1200000`.
- Mong đợi: giá trị `1200000` (hoặc `1,200,000` nếu trang tự định dạng), không lặp và không dư ký tự.

**BUG-002 — Chrome Autocomplete Extra Character**

1. Gõ `Q` vào ô input có lịch sử autocomplete.
2. Chrome gợi ý `Quên chấm công`.
3. Chọn gợi ý (bằng chuột và bằng phím mũi tên + Enter, test cả hai).
4. Mong đợi: `Quên chấm công`, không phải `Quên chấm côngQ`.
5. Biến thể: gõ `Quee` (có biến đổi) rồi chọn gợi ý.

**BUG-003 — Chrome Omnibox Navigation**

1. Bật chế độ tiếng Việt.
2. Gõ `lo` trên thanh địa chỉ.
3. Chrome gợi ý inline `localhost:8081`.
4. Nhấn **Enter trực tiếp**.
5. Mong đợi: điều hướng tới `localhost:8081`, giống chế độ English.
6. Biến thể: gõ một từ có dấu trên omnibox khi đang có inline suggestion.

**BUG-004 — Từ chưa hoàn thiện cho tới khi nhấn Space**

1. Trong terminal và trong ô nhập của Chrome, gõ `vieejt` nhưng không nhấn Space.
2. Mong đợi: `việt` đã nằm trong ứng dụng (không gạch chân). Chuyển focus, click chỗ khác hoặc nhấn phím điều hướng không làm mất hay nhân đôi chữ.

**Bổ sung khi phát hiện:** lỗi trong VS Code (editor, Quick Open `Ctrl+P`, Command Palette, terminal tích hợp) được thêm vào đây theo cùng mẫu.

### 8.4. Xác định nguyên nhân

So sánh hành vi giữa `ibus-unikey`, Telexiva ở từng strategy và English trên cùng một ô, dùng log sự kiện của playground. Chỉ đánh dấu "đã sửa" khi tái lập được; ghi rõ giới hạn nếu nguyên nhân nằm ngoài engine (trong Chrome, Mutter hoặc IBus daemon).

## 9. Lộ trình phát triển

### Phase 0 — Research, playground & prototype

1. Thiết lập compiler/CMake/debugger, khởi tạo Git và README.
2. Viết playground HTML (FR-008).
3. Tái hiện bốn lỗi với `ibus-unikey`, ghi lại log sự kiện.
4. **Prototype IBus engine bằng Python** (`python3-ibus` / GObject Introspection, đã có sẵn trên máy): Telex tối giản (`aa`, `dd`, `w`, dấu thanh) + pass-through first + S2 + guard + S3.
5. Chạy prototype song song với `ibus-unikey` (Phụ lục A); kiểm chứng:
   - Chrome native Wayland có cung cấp surrounding text và nhận `delete_surrounding_text` không.
   - Ba lỗi Chrome và BUG-004 có hết với pass-through first không.
   - `forward_key_event(BackSpace)` hoạt động và đúng thứ tự trong terminal trên Wayland không.
   - Engine lấy được thông tin ứng dụng (cho FR-010) và hiện được trạng thái V/E trên top bar không.
6. Tìm vòng lặp phát triển không cần `sudo` (chạy engine từ thư mục build).

**Deliverable:** repository build được; playground; prototype; báo cáo kiểm chứng; ADR 0001 cập nhật kết quả. **Cổng quyết định:** nếu S2 không hoạt động trong Chrome, xem lại FR-009 trước khi sang Phase 1.

### Phase 1 — Telexiva Core

Engine API (`EditAction`), state machine, mô hình âm tiết, Telex đầy đủ theo FR-001, kiểm tra chính tả và tự khôi phục, backspace/reset, unit test dạng bảng, fuzz, benchmark. **Deliverable:** core độc lập IBus, test xanh, đạt NFR-001 cho core.

### Phase 2 — IBus Engine (C++)

Wrapper GObject, đăng ký engine, nhận key event, strategy S2 + S3 + guard, input context, ô mật khẩu, chuyển chế độ V/E, indicator. **Deliverable:** thay prototype bằng engine C++; gõ tiếng Việt được hằng ngày trong ứng dụng GTK.

### Phase 3 — Chrome, VS Code & Regression

Kiểm thử theo ma trận NFR-003; chạy các lỗi §8.3 với từng strategy; app profile (FR-010); S1 nếu cần. **Deliverable:** compatibility matrix và báo cáo regression.

### Phase 4 — Settings

Theo FR-007. **Deliverable:** cấu hình được mọi tùy chọn qua giao diện, mở được từ menu input source của GNOME.

### Phase 5 — Packaging & Release

Debian package (engine, component XML, GSettings schema, settings app), hướng dẫn cài/gỡ/rollback, kiểm thử nâng cấp, tài liệu và release notes. **Deliverable:** `.deb` thử nghiệm và GitHub release.

## 10. Tiêu chí hoàn thành MVP

- [ ] Core qua toàn bộ bảng test của FR-001 (kể cả tự khôi phục từ tiếng Anh).
- [ ] Fuzz test và benchmark đạt NFR-001, NFR-002.
- [ ] IBus engine C++ chạy trên GNOME Wayland, song song với engine khác.
- [ ] Gõ được tiếng Việt trong Chrome (Wayland), VS Code editor và terminal.
- [ ] Pass-through first: không có preedit mặc định; phím không biến đổi đi thẳng tới ứng dụng.
- [ ] Strategy S2 (kèm guard) và S3; tự chọn theo capability của client.
- [ ] Chuyển Vietnamese / English bằng phím tắt cấu hình được, có indicator.
- [ ] Ô mật khẩu tự pass-through.
- [ ] Xử lý backspace, reset, focus change, context destroy.
- [ ] Không ảnh hưởng bộ gõ hiện tại khi chưa được chọn.
- [ ] Có hướng dẫn build, cài đặt và rollback.
- [ ] Có báo cáo regression cho bốn lỗi ở §8.3.

Sửa được tất cả các lỗi là mục tiêu, nhưng **không phải điều kiện bắt buộc của MVP** nếu chứng minh được nguyên nhân nằm ngoài engine. MVP phải chỉ ra được strategy nào khắc phục lỗi nào.

## 11. Rủi ro kỹ thuật

| Rủi ro | Hướng xử lý |
|---|---|
| Chrome native Wayland không cung cấp surrounding text qua Mutter → IBus | Kiểm chứng bằng prototype ở Phase 0; dự phòng S3 hoặc S1 cho Chrome |
| `forward_key_event` trên Wayland sai thứ tự với `commit_text` | Kiểm chứng ở Phase 0; nếu sai, terminal dùng S1 |
| Không phân biệt được editor và terminal tích hợp trong VS Code | Dựa vào capability surrounding text; nếu không được, chọn strategy an toàn chung cho VS Code |
| Không lấy được tên ứng dụng trên Wayland (FR-010) | Kiểm chứng ở Phase 0; dự phòng chọn strategy chỉ dựa trên capability |
| Chrome xử lý composition khác GTK/Qt | Playground + regression test theo strategy |
| Quy tắc tiếng Việt nhiều trường hợp biên | Bảng test dữ liệu từ sớm, đối chiếu UniKey |
| Từ tiếng Anh trùng âm tiết tiếng Việt không được khôi phục | Chấp nhận như UniKey; whitelist ở P2 |
| API IBus / hành vi Mutter thay đổi giữa các bản GNOME | Ghim theo Ubuntu 26.04; ghi phiên bản trong compatibility matrix |
| Khó debug sự kiện phím | Playground và logging không chứa dữ liệu nhạy cảm |

## 12. Quy ước phát triển

### 12.1. Coding Standards

C++20, RAII (kể cả wrapper cho đối tượng GObject), tách core khỏi IBus, hạn chế global mutable state, không để exception thoát khỏi core, unit test cho thay đổi quan trọng, clang-format và clang-tidy.

### 12.2. Git Workflow

- `main`: ổn định.
- `feature/*`: chức năng.
- `fix/*`: sửa lỗi.
- `docs/*`: tài liệu.

```text
feat(core): implement basic telex transformation
fix(ibus): reset composition on focus change
test(core): add tone placement regression cases
docs: add Ubuntu development guide
```

### 12.3. Issue Tracking

Mỗi issue cần: môi trường (OS, GNOME, engine + phiên bản, ứng dụng + phiên bản, Wayland/XWayland, chế độ gõ, commit strategy), bước tái hiện, kết quả thực tế, kết quả mong đợi, log kỹ thuật (nếu có), trạng thái xác minh nguyên nhân.

## 13. Nguyên tắc triển khai

1. **Core first:** kiểm thử logic trước khi tích hợp hệ thống.
2. **Measure first:** có playground và prototype trước khi kết luận nguyên nhân lỗi.
3. **Pass-through first:** không can thiệp khi không cần; không bao giờ xóa chữ khi không chắc.
4. **Incremental development:** phát triển từng chức năng nhỏ.
5. **UniKey parity:** khi mơ hồ, hành vi UniKey Windows là chuẩn.
6. **Safe installation:** không tự động gỡ, thay thế hay chuyển khỏi engine người dùng đang dùng.
7. **Privacy by design:** không thu thập nội dung người dùng nhập.
8. **Open architecture:** core độc lập để mở rộng sang Fcitx5 và bản phân phối khác.

## 14. Định hướng dài hạn

VNI (FR-002), gõ tắt (FR-012), whitelist từ tiếng Anh, frontend Fcitx5 cho KDE/Sway/Hyprland, tự động hóa integration test trên Chrome, hỗ trợ bản phân phối khác, cộng đồng đóng góp.

## 15. Câu hỏi còn mở

| # | Câu hỏi | Chốt khi |
|---|---|---|
| Q1 | ~~Framework: Fcitx5 hay IBus?~~ **Đã chốt: IBus** (§6.0) | v0.3.0 |
| Q2 | License: GPL-3.0-or-later? (bắt buộc nếu tham khảo mã UniKey/Bamboo) | Trước commit đầu tiên |
| Q3 | URL thật để tái hiện BUG-001 | Phase 0 |
| Q4 | Chrome native Wayland có hỗ trợ surrounding text qua IBus không? | Phase 0 (prototype) |
| Q5 | Phím tắt mặc định `Ctrl+Shift` có xung đột thực tế trong VS Code không? | Phase 2 |
| Q6 | Settings app dùng GTK4/libadwaita hay Qt6? | Phase 4 |

## 16. Kết luận

Telexiva vừa là bộ gõ tiếng Việt cho web developer trên Ubuntu GNOME, vừa là môi trường học phát triển phần mềm native Linux. Ba giá trị cốt lõi:

- **Correctness:** gõ chính xác, giống UniKey, không bao giờ xóa nhầm chữ.
- **Compatibility:** ổn định trong Chrome và VS Code trước, rồi mở rộng.
- **Maintainability:** core độc lập, có kiểm thử, dễ phát triển.

---

## Phụ lục A — Chạy Telexiva song song với `ibus-unikey`

Telexiva là một engine thêm vào IBus đang chạy, nên **không cần đổi im-config, không cần gỡ `ibus-unikey`**.

**Thêm engine (sau khi cài prototype hoặc bản build):**

1. Khởi động lại IBus để nạp component mới: `ibus restart`.
2. Settings → Keyboard → Input Sources → **+** → Vietnamese → **Telexiva**.
3. Dùng `Super+Space` để chuyển qua lại giữa Unikey và Telexiva khi so sánh.

**Kiểm tra engine đang chạy:**

```bash
ibus list-engine | grep -i -E 'telexiva|unikey'
ibus engine            # engine đang được dùng
```

**Rollback:**

1. Settings → Keyboard → Input Sources → xóa Telexiva.
2. Gỡ file component và binary (hoặc `sudo apt purge telexiva` khi đã có gói `.deb`).
3. `ibus restart`.

`ibus-unikey` và cấu hình của nó không bị đụng tới ở bất kỳ bước nào.

**Ghi chú về Fcitx5:** đã loại khỏi phạm vi MVP (§6.0). Nếu sau này cần thử Fcitx5 song song, phải ghim IBus bằng `im-config -n ibus` trước khi cài, vì im-config đang ở chế độ auto và có thể tự chuyển sang Fcitx5.
