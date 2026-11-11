// SPDX-License-Identifier: GPL-3.0-or-later
//
// Engine: thực hiện EditAction của Composer trong một ứng dụng thật (FR-009).
//
// Không phụ thuộc IBus: mọi tương tác với ứng dụng đi qua giao diện Host, nên test
// được bằng một ô nhập giả (tests/engine). Lớp nối IBus nằm ở src/ibus.
//
// Chuyển từ prototype/telexiva_proto.py, giữ các bài học Phase 0:
//   - pass-through first (Composer);
//   - S2: delete_surrounding_text + commit; bù byte khi bản sao của Mutter còn cũ;
//   - đợi ô nhập xác nhận lần sửa trước (tối đa wait_ms), phím đến trong lúc đợi được xếp hàng;
//   - sửa hai bước khi có vùng chọn sau con trỏ (gợi ý tự điền của thanh địa chỉ);
//   - guard: chịu được báo trễ / trạng thái giữa chừng, không bao giờ xóa đoán;
//   - kiểm tra sau khi sửa: ô làm sai -> tự chuyển sang preedit (S1) cho tới khi đổi focus.
#pragma once

#include <cstdint>
#include <deque>
#include <optional>
#include <string>
#include <vector>

#include "telexiva/composer.hpp"

namespace telexiva {

struct Surrounding {
    std::u32string text;
    std::uint32_t cursor = 0;
    std::uint32_t anchor = 0;
};

// Những gì Engine cần từ môi trường (IBus, hoặc ô nhập giả khi test).
class Host {
public:
    virtual ~Host() = default;
    virtual void commit(const std::string& utf8) = 0;
    virtual void delete_surrounding(int offset, unsigned nchars) = 0;
    virtual Surrounding surrounding() = 0;
    virtual void forward_key(std::uint32_t keyval, std::uint32_t keycode, std::uint32_t state) = 0;
    virtual void update_preedit(const std::string& utf8) = 0;
    virtual void hide_preedit() = 0;
    // Xử lý một lượt sự kiện đang chờ (vòng lặp sự kiện lồng nhau khi đợi xác nhận).
    virtual bool iterate_main_loop() = 0;
    virtual double now_ms() = 0;
    // Chỉ ghi số liệu, không bao giờ ghi nội dung người dùng gõ (NFR-004).
    virtual void log(const std::string& line) = 0;
};

enum class Strategy { Auto, Preedit /*S1*/, Surrounding /*S2*/, ForwardKeys /*S3*/ };

struct EngineConfig {
    TelexOptions telex;
    Strategy strategy = Strategy::Auto;
    bool guard = true;
    double wait_ms = 100.0;  // trang web nặng có thể mất ~50 ms để xác nhận một lần sửa
};

struct Key {
    enum class Kind { Letter, Printable, Enter, Tab, Backspace, Escape, Navigation, Modifier, Other };
    Kind kind = Kind::Other;
    char32_t ch = 0;        // ký tự của phím (0 nếu không có)
    bool release = false;
    bool shortcut = false;  // có Ctrl/Alt/Super
    std::uint32_t keyval = 0, keycode = 0, state = 0;  // để forward lại nguyên phím
};

enum class Purpose { FreeForm, Password, Pin, Terminal, Url, Other };

class Engine {
public:
    Engine(Host& host, EngineConfig config);

    // true = engine đã xử lý phím (ứng dụng không nhận phím gốc).
    bool process_key(const Key& key);

    void focus_in(const std::string& client);
    void focus_out();
    void reset();
    void set_capabilities(bool surrounding_text);
    void set_content_type(Purpose purpose, std::uint32_t hints);
    // Ô nhập vừa gửi surrounding text mới (= xác nhận lần sửa trước).
    void on_surrounding_changed();

    [[nodiscard]] bool preedit_mode() const { return preedit_mode_; }
    [[nodiscard]] Strategy effective_strategy() const;

private:
    struct PendingVerify {
        std::u32string expect, broken, ins;
        int tries = 3;
        double gap_ms = 0;
    };

    bool handle(const Key& key);
    void drain_queue();
    bool apply_edit(const std::u32string& old, const EditAction& action);
    bool guard_ok(const std::u32string& old);
    unsigned mutter_safe_delete_count(const std::u32string& to_delete);
    bool selection_after_cursor();
    void wait_confirm();
    void check_pending_verify();
    void note_shown(const std::u32string& old, const std::u32string& now);
    void reset_word(const char* why);

    bool process_preedit(const Key& key);
    void show_preedit();
    void commit_preedit(bool final);

    void log(const std::string& line);

    Host& host_;
    EngineConfig config_;
    Composer composer_;

    bool has_surrounding_ = false;
    Purpose purpose_ = Purpose::FreeForm;
    std::uint32_t hints_ = 0;
    std::string client_ = "?";

    std::vector<std::u32string> recent_;                   // các trạng thái shown trước đó
    std::optional<std::pair<std::u32string, double>> inflight_;  // chữ sau khi xóa, thời điểm
    std::optional<PendingVerify> pending_;
    std::optional<double> awaiting_confirm_;
    double last_edit_at_ = -1e9;
    bool waiting_ = false;
    std::deque<Key> queue_;

    bool preedit_mode_ = false;  // ô này bỏ qua / làm sai lệnh xóa -> dùng nháp
    std::string preedit_raw_;
    std::u32string preedit_shown_;
};

}  // namespace telexiva
