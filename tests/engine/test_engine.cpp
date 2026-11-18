// SPDX-License-Identifier: GPL-3.0-or-later
//
// Test Engine với ô nhập giả (FakeHost), chuyển từ prototype/test_engine_sim.py.
#include <catch2/catch_test_macros.hpp>

#include <cctype>
#include <string>
#include <vector>

#include "telexiva/engine.hpp"

using namespace telexiva;

namespace {

// Ô nhập giả, mô phỏng Chrome qua Mutter (GNOME Wayland) ở mức đủ cho các ca đã gặp.
struct FakeHost : Host {
    std::u32string buf;         // nội dung thật trước con trỏ
    std::u32string sel;         // vùng chọn sau con trỏ (gợi ý tự điền của thanh địa chỉ)
    std::u32string after;       // chữ sau con trỏ, không chọn (sửa giữa từ)
    bool mode_vi = true;
    std::u32string view;        // bản sao của Mutter (khi stale_mode)
    bool stale_mode = false;    // engine thấy `view` thay vì `buf`; Mutter đổi ký tự -> byte bằng view
    bool ignore_delete = false; // ô kiểu ChatGPT: bỏ qua lệnh xóa
    int delete_extra = 0;       // ô xóa thừa N ký tự (gống)
    std::string preedit;
    double t = 0;
    std::vector<std::string> logs;

    void commit(const std::string& utf8) override {
        sel.clear();  // chữ chèn thay vùng chọn
        buf += utf8_to_u32(utf8);
    }
    void delete_surrounding(int offset, unsigned nchars) override {
        (void)nchars;
        if (ignore_delete || !sel.empty()) {
            return;  // Chrome bỏ qua lệnh xóa khi có vùng chọn
        }
        if (stale_mode) {
            // Mutter: đổi ký tự -> byte bằng bản sao; Chrome xóa theo byte trên nội dung thật.
            const std::u32string tail = view.substr(view.size() - static_cast<std::size_t>(-offset));
            std::string raw = u32_to_utf8(buf);
            const std::size_t nbytes = u32_to_utf8(tail).size();
            raw.resize(raw.size() - std::min(nbytes, raw.size()));
            // Cắt giữa một ký tự UTF-8 -> Chrome bỏ cả lệnh xóa.
            if (!raw.empty() && (static_cast<unsigned char>(raw.back()) & 0xC0) == 0xC0) {
                return;
            }
            if (u32_to_utf8(utf8_to_u32(raw)) != raw || utf8_to_u32(raw).find(U'�') != std::u32string::npos) {
                return;
            }
            buf = utf8_to_u32(raw);
            return;
        }
        const std::size_t before = static_cast<std::size_t>(-offset);
        const std::size_t n = before + static_cast<std::size_t>(delete_extra);
        buf.resize(buf.size() - std::min(n, buf.size()));
        if (nchars > before) {
            after.erase(0, std::min<std::size_t>(nchars - before, after.size()));
        }
    }
    Surrounding surrounding() override {
        if (stale_mode) {
            return {view, static_cast<std::uint32_t>(view.size()), static_cast<std::uint32_t>(view.size())};
        }
        const std::u32string all = buf + sel + after;
        return {all, static_cast<std::uint32_t>(buf.size()), static_cast<std::uint32_t>(buf.size() + sel.size())};
    }
    void forward_key(std::uint32_t, std::uint32_t, std::uint32_t) override {}  // Wayland: không tới app
    void update_preedit(const std::string& utf8) override { preedit = utf8; }
    void hide_preedit() override { preedit.clear(); }
    bool iterate_main_loop() override {
        t += 1;
        return false;
    }
    double now_ms() override { return t; }
    void log(const std::string& line) override { logs.push_back(line); }
    void mode_changed(bool vietnamese) override { mode_vi = vietnamese; }

    [[nodiscard]] std::string text() const { return u32_to_utf8(buf + after); }
};

struct Session {
    FakeHost host;
    Engine engine;
    bool auto_confirm = true;
    std::u32string history;   // "lịch sử duyệt web" để mô phỏng gợi ý tự điền (rỗng = không có)
    bool stale_next = false;

    explicit Session(EngineConfig cfg = {}) : engine(host, cfg) {
        engine.set_capabilities(true);
        engine.focus_in("test");
    }

    Session& type(const std::string& keys) {
        for (const char c : keys) {
            host.t += 80;  // khoảng cách giữa hai phím
            if (host.stale_mode) {
                if (!stale_next) {
                    host.view = host.buf;  // Mutter cập nhật bản sao, trừ ngay sau một lần sửa
                }
                stale_next = false;
            } else if (auto_confirm) {
                engine.on_surrounding_changed();
            }
            Key k;
            k.ch = static_cast<unsigned char>(c);
            const bool letter = std::isalpha(static_cast<unsigned char>(c)) != 0 || c == '[' || c == ']' ||
                                c == '{' || c == '}';
            k.kind = letter ? Key::Kind::Letter : Key::Kind::Printable;
            if (c == '\b') {  // Backspace
                k.kind = Key::Kind::Backspace;
                k.ch = 0;
                if (!engine.process_key(k) && !host.buf.empty()) {
                    host.buf.pop_back();  // ứng dụng tự xóa ký tự trước con trỏ
                }
                continue;
            }
            const std::size_t logs_before = host.logs.size();
            if (!engine.process_key(k)) {
                host.sel.clear();
                host.buf.push_back(k.ch);  // ứng dụng tự chèn phím đi thẳng
            }
            for (std::size_t i = logs_before; i < host.logs.size(); ++i) {
                if (host.logs[i].find("replace") != std::string::npos) {
                    stale_next = true;
                }
            }
            if (!history.empty()) {
                const bool prefix = !host.buf.empty() && history.compare(0, host.buf.size(), host.buf) == 0;
                host.sel = prefix ? history.substr(host.buf.size()) : U"";
            }
        }
        return *this;
    }
    [[nodiscard]] std::string text() const { return host.text(); }

    // Phím bổ trợ (Ctrl/Shift) để thử phím tắt chuyển chế độ.
    bool key(std::uint32_t keyval, std::uint32_t state, bool release, Key::Kind kind = Key::Kind::Modifier) {
        Key k;
        k.kind = kind;
        k.keyval = keyval;
        k.state = state | (release ? (1u << 30) : 0u);
        k.release = release;
        k.shortcut = kind != Key::Kind::Modifier && (state & 4u) != 0;
        return engine.process_key(k);
    }
    void ctrl_shift() {
        key(0xffe3, 0, false);       // Ctrl xuống
        key(0xffe1, 4, false);       // Shift xuống (đang giữ Ctrl)
        key(0xffe1, 4 | 1, true);    // Shift lên
        key(0xffe3, 4, true);        // Ctrl lên
    }
    bool escape() {
        Key k;
        k.kind = Key::Kind::Escape;
        return engine.process_key(k);
    }
};


}  // namespace

TEST_CASE("Engine: câu tiếng Việt qua S2", "[engine]") {
    CHECK(Session{}.type("Vieejt Nam ddepj quas ").text() == "Việt Nam đẹp quá ");
    CHECK(Session{}.type("dudocwj chuaw ").text() == "được chưa ");
}

TEST_CASE("Engine: số và chữ không biến đổi đi thẳng (BUG-001, BUG-003)", "[engine]") {
    Session s;
    s.type("1200000 lo");
    CHECK(s.text() == "1200000 lo");
    CHECK(s.host.preedit.empty());
}

TEST_CASE("Engine: chọn gợi ý sau khi gõ Q không dư chữ (BUG-002)", "[engine]") {
    Session s;
    s.type("Q");
    s.host.buf = U"Quên chấm công";  // Chrome thay giá trị khi chọn gợi ý
    s.engine.focus_out();
    CHECK(s.text() == "Quên chấm công");
}

TEST_CASE("Engine: trang tự đổi nội dung thì không xóa nhầm", "[engine]") {
    Session s;
    s.type("Quee");
    s.host.buf = U"Quên chấm công";
    s.type("s");
    // Không xóa nhầm nội dung trang; phím dấu ngay sau từ "công" sửa dấu từ đó (nhặt lại từ).
    CHECK(s.text() == "Quên chấm cống");
    CHECK_FALSE(s.engine.preedit_mode());
}

TEST_CASE("Engine: ô bỏ qua lệnh xóa -> tự chuyển sang nháp", "[engine]") {
    Session s;
    s.host.ignore_delete = true;
    s.type("taoj vaanx conf ");
    CHECK(s.text() == "taoạo vẫn còn ");  // từ đầu sai (đã biết), sau đó đúng
    CHECK(s.engine.preedit_mode());
}

TEST_CASE("Engine: ô xóa thừa -> tự chuyển sang nháp", "[engine]") {
    Session s;
    s.host.delete_extra = 1;
    s.type("giongso ");
    CHECK(s.engine.preedit_mode());
    const std::size_t start = s.host.buf.size();
    s.type("dduowcj ");
    CHECK(u32_to_utf8(s.host.buf.substr(start)) == "được ");
}

TEST_CASE("Engine: preedit hiển thị nháp, chốt khi kết thúc từ", "[engine]") {
    EngineConfig cfg;
    cfg.strategy = Strategy::Preedit;
    Session s(cfg);
    s.type("dduowcj");
    CHECK(s.text().empty());
    CHECK(s.host.preedit == "được");
    s.type(" ");
    CHECK(s.text() == "được ");
}

TEST_CASE("Engine: thanh địa chỉ có gợi ý tự điền, mọi từ (sửa hai bước)", "[engine]") {
    const std::vector<std::tuple<std::string, std::u32string, std::string>> cases = {
        {"gox", U"google.com", "gõ"},        {"tieengs", U"tiki.vn", "tiếng"},
        {"vieejt", U"viblo.asia", "việt"},   {"dduowcj", U"docs.google.com", "được"},
        {"nguowif", U"nguoiquansat.vn", "người"}, {"khoong", U"khoahoc.tv", "không"},
        {"lo", U"localhost:8081", "lo"},
    };
    for (const auto& [keys, history, want] : cases) {
        INFO(keys);
        Session s;
        s.history = history;
        s.type(keys);
        s.history.clear();
        s.type(" ");
        CHECK(s.text() == want + " ");
    }
}

TEST_CASE("Engine: bản sao cũ của Mutter được bù byte (gócốc)", "[engine]") {
    Session s;
    s.host.stale_mode = true;
    s.type("gocso ");
    CHECK(s.text() == "gốc ");
}

TEST_CASE("Engine: ô mật khẩu không biến đổi (FR-011)", "[engine]") {
    Session s;
    s.engine.set_content_type(Purpose::Password, 0);
    s.type("aas");
    CHECK(s.text() == "aas");
}

TEST_CASE("Engine: ngữ cảnh code, URL, email (FR-013)", "[engine]") {
    for (const char* text : {"foo_bar ", "api/test ", "test@example.com ", "$var "}) {
        INFO(text);
        CHECK(Session{}.type(text).text() == text);
    }
}

TEST_CASE("Engine: log không chứa nội dung người dùng gõ (NFR-004)", "[engine]") {
    Session s;
    s.type("Vieejt Nam bimaatj ");
    for (const auto& line : s.host.logs) {
        INFO(line);
        CHECK(line.find("Việt") == std::string::npos);
        CHECK(line.find("mật") == std::string::npos);
        CHECK(line.find("bimaat") == std::string::npos);
    }
}

TEST_CASE("Engine: Backspace rồi đổi dấu trong lúc gõ", "[engine][edit]") {
    CHECK(Session{}.type("vieejt\bst ").text() == "viết ");   // việt -> việ -> viế -> viết
    CHECK(Session{}.type("hocj\b\bas ").text() == "há ");    // học -> họ -> h -> há
}

TEST_CASE("Engine: quay lại sửa dấu một từ đã gõ xong", "[engine][edit]") {
    CHECK(Session{}.type("hocj \bs ").text() == "hóc ");       // học, Space, Backspace, s -> hóc
    CHECK(Session{}.type("Vieejt \bs ").text() == "Viết ");
    CHECK(Session{}.type("nha \bf ").text() == "nhà ");        // từ không dấu vẫn nhặt lại được
}

TEST_CASE("Engine: không nhặt lại từ tiếng Anh", "[engine][edit]") {
    static WordSet words;
    words.insert("ban");
    EngineConfig cfg;
    cfg.telex.english = &words;
    CHECK(Session{cfg}.type("ban \bs ").text() == "bans ");   // không thành "bán"
    CHECK(Session{}.type("ban \bs ").text() == "bán ");       // không có từ điển: nhặt lại
}

TEST_CASE("Engine: Ctrl+Shift chuyển Việt/Anh (FR-004)", "[engine][mode]") {
    Session s;
    s.ctrl_shift();
    CHECK_FALSE(s.engine.vietnamese());
    CHECK_FALSE(s.host.mode_vi);
    s.type("vieejt ");
    CHECK(s.text() == "vieejt ");  // English: đi thẳng
    s.ctrl_shift();
    CHECK(s.engine.vietnamese());
    s.type("vieejt ");
    CHECK(s.text() == "vieejt việt ");
}

TEST_CASE("Engine: Ctrl+Shift+P (VS Code) không chuyển chế độ", "[engine][mode]") {
    Session s;
    s.key(0xffe3, 0, false);
    s.key(0xffe1, 4, false);
    s.key('P', 4 | 1, false, Key::Kind::Letter);  // có phím khác xen giữa
    s.key(0xffe1, 4 | 1, true);
    s.key(0xffe3, 4, true);
    CHECK(s.engine.vietnamese());
}

TEST_CASE("Engine: Esc khôi phục chuỗi phím gốc khi đoán sai", "[engine][restore]") {
    Session s;
    s.type("tes");                 // tes -> té
    CHECK(s.text() == "té");
    CHECK(s.escape());             // Esc được dùng để khôi phục
    CHECK(s.text() == "tes");
    s.type("t ");                  // phần còn lại của từ giữ nguyên
    CHECK(s.text() == "test ");
    CHECK_FALSE(Session{}.escape());  // không có từ đang gõ: Esc đi thẳng (đóng hộp thoại…)
}

TEST_CASE("Engine: sửa dấu thanh khi con trỏ ở giữa từ", "[engine][edit]") {
    Session s;
    s.host.buf = U"hoa";
    s.host.after = U"ng nhé";
    s.engine.focus_in("test");
    s.type("f");
    CHECK(s.text() == "hoàng nhé");
    Session t;
    t.host.buf = U"hoa";
    t.host.after = U"ng";
    t.engine.focus_in("test");
    t.type("n");                   // chữ thường giữa từ: chèn như bình thường
    CHECK(t.text() == "hoanng");
}

TEST_CASE("Engine: gõ tắt (FR-012)", "[engine][macro]") {
    static MacroTable macros;
    macros.add("ko", U"không");
    macros.add("vn", U"Việt Nam");
    EngineConfig cfg;
    cfg.macros = &macros;
    CHECK(Session{cfg}.type("ko bt, vn. ").text() == "không bt, Việt Nam. ");
    CHECK(Session{cfg}.type("Ko KO ").text() == "Không KHÔNG ");
    CHECK(Session{cfg}.type("foo_ko kon ").text() == "foo_ko kon ");  // code, từ khác: không đổi
}

TEST_CASE("Engine: từ viết tắt IN HOA giữ nguyên", "[engine]") {
    CHECK(Session{}.type("AWS OS REST CORS UX API os ").text() == "AWS OS REST CORS UX API ó ");
}
