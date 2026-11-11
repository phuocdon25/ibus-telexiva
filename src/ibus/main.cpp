// SPDX-License-Identifier: GPL-3.0-or-later
//
// ibus-engine-telexiva: nối telexiva::Engine với IBus.
//
// Lớp này mỏng: chuyển sự kiện IBus -> Engine, và cài đặt Host bằng API IBus.
// Mọi quyết định nằm trong src/engine (test được không cần IBus).
//
// Chạy bởi ibus-daemon:  ibus-engine-telexiva --ibus
// Chạy tay để debug:     ibus-engine-telexiva   (tự đăng ký component)
#include <ibus.h>

#include <unistd.h>

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <memory>
#include <string>

#include "telexiva/engine.hpp"

namespace {

constexpr const char* kEngineName = "telexiva";
constexpr const char* kBusName = "org.freedesktop.IBus.Telexiva";

// ---------------------------------------------------------------------------
// Log (chỉ số liệu) và cấu hình
// ---------------------------------------------------------------------------

std::string xdg_dir(const char* env, const char* fallback) {
    if (const char* v = std::getenv(env); v != nullptr && *v != '\0') {
        return v;
    }
    const char* home = std::getenv("HOME");
    return std::string(home ? home : "/tmp") + "/" + fallback;
}

class FileLog {
public:
    FileLog() {
        const std::filesystem::path dir = std::filesystem::path(xdg_dir("XDG_CACHE_HOME", ".cache")) / "telexiva";
        std::error_code ec;
        std::filesystem::create_directories(dir, ec);
        path_ = dir / "engine.log";
        if (std::filesystem::exists(path_, ec) && std::filesystem::file_size(path_, ec) > 1'000'000) {
            std::filesystem::rename(path_, dir / "engine.log.1", ec);  // xoay vòng đơn giản
        }
        out_.open(path_, std::ios::app);
    }
    void write(const std::string& line) {
        if (!out_) {
            return;
        }
        const auto now = std::chrono::system_clock::now();
        const std::time_t tt = std::chrono::system_clock::to_time_t(now);
        const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(now.time_since_epoch()).count() % 1000;
        std::tm tm{};
        localtime_r(&tt, &tm);
        char ts[32];
        std::snprintf(ts, sizeof ts, "%02d:%02d:%02d.%03d", tm.tm_hour, tm.tm_min, tm.tm_sec, static_cast<int>(ms));
        out_ << ts << ' ' << line << '\n';
        out_.flush();
    }

private:
    std::filesystem::path path_;
    std::ofstream out_;
};

FileLog& file_log() {
    static FileLog log;
    return log;
}

const telexiva::WordSet& english() {
    static const telexiva::WordSet words = telexiva::WordSet::load_default();
    return words;
}

// ~/.config/telexiva.conf, dạng key = value:
//   tone = old | new          (kiểu đặt dấu)
//   strategy = auto | s1 | s2 (ép cách sửa chữ, để thử nghiệm)
//   guard = on | off
telexiva::EngineConfig load_config() {
    telexiva::EngineConfig cfg;
    cfg.telex.english = &english();
    std::ifstream in(xdg_dir("XDG_CONFIG_HOME", ".config") + "/telexiva.conf");
    std::string line;
    while (std::getline(in, line)) {
        line = line.substr(0, line.find('#'));
        const auto eq = line.find('=');
        if (eq == std::string::npos) {
            continue;
        }
        auto trim = [](std::string s) {
            const auto b = s.find_first_not_of(" \t");
            const auto e = s.find_last_not_of(" \t\r");
            return b == std::string::npos ? std::string() : s.substr(b, e - b + 1);
        };
        const std::string key = trim(line.substr(0, eq));
        const std::string value = trim(line.substr(eq + 1));
        if (key == "tone") {
            cfg.telex.new_style = value == "new";
        } else if (key == "strategy") {
            cfg.strategy = value == "s1"   ? telexiva::Strategy::Preedit
                           : value == "s2" ? telexiva::Strategy::Surrounding
                                           : telexiva::Strategy::Auto;
        } else if (key == "guard") {
            cfg.guard = value != "off";
        }
    }
    return cfg;
}

// ---------------------------------------------------------------------------
// Host bằng API IBus
// ---------------------------------------------------------------------------

class IBusHost : public telexiva::Host {
public:
    explicit IBusHost(IBusEngine* engine) : engine_(engine) {}

    void commit(const std::string& utf8) override {
        ibus_engine_commit_text(engine_, ibus_text_new_from_string(utf8.c_str()));
    }
    void delete_surrounding(int offset, unsigned nchars) override {
        ibus_engine_delete_surrounding_text(engine_, offset, nchars);
    }
    telexiva::Surrounding surrounding() override {
        IBusText* text = nullptr;  // transfer none
        guint cursor = 0;
        guint anchor = 0;
        ibus_engine_get_surrounding_text(engine_, &text, &cursor, &anchor);
        telexiva::Surrounding s;
        if (text != nullptr && ibus_text_get_text(text) != nullptr) {
            s.text = telexiva::utf8_to_u32(ibus_text_get_text(text));
        }
        s.cursor = cursor;
        s.anchor = anchor;
        return s;
    }
    void forward_key(std::uint32_t keyval, std::uint32_t keycode, std::uint32_t state) override {
        ibus_engine_forward_key_event(engine_, keyval, keycode, state);
    }
    void update_preedit(const std::string& utf8) override {
        IBusText* text = ibus_text_new_from_string(utf8.c_str());
        const guint len = ibus_text_get_length(text);
        ibus_text_append_attribute(text, IBUS_ATTR_TYPE_UNDERLINE, IBUS_ATTR_UNDERLINE_SINGLE, 0, len);
        // COMMIT: khi ô mất focus, IBus tự chốt phần nháp (giống ibus-unikey).
        ibus_engine_update_preedit_text_with_mode(engine_, text, len, TRUE, IBUS_ENGINE_PREEDIT_COMMIT);
    }
    void hide_preedit() override { ibus_engine_hide_preedit_text(engine_); }
    bool iterate_main_loop() override {
        if (g_main_context_iteration(nullptr, FALSE)) {
            return true;
        }
        g_usleep(500);
        return false;
    }
    double now_ms() override { return static_cast<double>(g_get_monotonic_time()) / 1000.0; }
    void log(const std::string& line) override { file_log().write(line); }

private:
    IBusEngine* engine_;
};

telexiva::Purpose to_purpose(guint purpose) {
    switch (purpose) {
        case IBUS_INPUT_PURPOSE_PASSWORD: return telexiva::Purpose::Password;
        case IBUS_INPUT_PURPOSE_PIN: return telexiva::Purpose::Pin;
        case IBUS_INPUT_PURPOSE_TERMINAL: return telexiva::Purpose::Terminal;
        case IBUS_INPUT_PURPOSE_URL: return telexiva::Purpose::Url;
        case IBUS_INPUT_PURPOSE_FREE_FORM: return telexiva::Purpose::FreeForm;
        default: return telexiva::Purpose::Other;
    }
}

telexiva::Key to_key(guint keyval, guint keycode, guint state) {
    using K = telexiva::Key::Kind;
    telexiva::Key k;
    k.keyval = keyval;
    k.keycode = keycode;
    k.state = state;
    k.release = (state & IBUS_RELEASE_MASK) != 0;
    k.shortcut = (state & (IBUS_CONTROL_MASK | IBUS_MOD1_MASK | IBUS_SUPER_MASK | IBUS_MOD4_MASK)) != 0;
    k.ch = ibus_keyval_to_unicode(keyval);
    switch (keyval) {
        case IBUS_KEY_Shift_L: case IBUS_KEY_Shift_R: case IBUS_KEY_Control_L: case IBUS_KEY_Control_R:
        case IBUS_KEY_Alt_L: case IBUS_KEY_Alt_R: case IBUS_KEY_Super_L: case IBUS_KEY_Super_R:
        case IBUS_KEY_Caps_Lock: case IBUS_KEY_ISO_Level3_Shift: case IBUS_KEY_Meta_L: case IBUS_KEY_Meta_R:
            k.kind = K::Modifier;
            return k;
        case IBUS_KEY_Return: case IBUS_KEY_KP_Enter:
            k.kind = K::Enter;
            return k;
        case IBUS_KEY_Tab:
            k.kind = K::Tab;
            return k;
        case IBUS_KEY_BackSpace:
            k.kind = K::Backspace;
            return k;
        case IBUS_KEY_Escape:
            k.kind = K::Escape;
            return k;
        default:
            break;
    }
    const bool ascii_letter = k.ch < 0x80 && (g_ascii_isalpha(static_cast<gchar>(k.ch)) || k.ch == '[' ||
                                               k.ch == ']' || k.ch == '{' || k.ch == '}');
    if (k.ch != 0 && ascii_letter) {
        k.kind = K::Letter;
    } else if (k.ch != 0 && g_unichar_isprint(k.ch)) {
        k.kind = K::Printable;
    } else {
        k.kind = K::Navigation;
    }
    return k;
}

}  // namespace

// ---------------------------------------------------------------------------
// GObject: TelexivaEngine kế thừa IBusEngine
// ---------------------------------------------------------------------------

struct TelexivaEngine {
    IBusEngine parent;
    IBusHost* host;
    telexiva::Engine* impl;
};

struct TelexivaEngineClass {
    IBusEngineClass parent;
};

G_DEFINE_TYPE(TelexivaEngine, telexiva_engine, IBUS_TYPE_ENGINE)

#define TELEXIVA_ENGINE(obj) (reinterpret_cast<TelexivaEngine*>(obj))

static void telexiva_engine_init(TelexivaEngine* self) {
    self->host = new IBusHost(IBUS_ENGINE(self));
    self->impl = new telexiva::Engine(*self->host, load_config());
}

static void telexiva_engine_destroy(IBusObject* object) {
    TelexivaEngine* self = TELEXIVA_ENGINE(object);
    delete self->impl;
    self->impl = nullptr;
    delete self->host;
    self->host = nullptr;
    IBUS_OBJECT_CLASS(telexiva_engine_parent_class)->destroy(object);
}

static gboolean telexiva_engine_process_key_event(IBusEngine* engine, guint keyval, guint keycode, guint state) {
    TelexivaEngine* self = TELEXIVA_ENGINE(engine);
    return self->impl != nullptr && self->impl->process_key(to_key(keyval, keycode, state)) ? TRUE : FALSE;
}

static void telexiva_engine_focus_in(IBusEngine* engine) {
    TelexivaEngine* self = TELEXIVA_ENGINE(engine);
    // IBus chỉ gửi surrounding text khi engine đã hỏi ít nhất một lần.
    ibus_engine_get_surrounding_text(engine, nullptr, nullptr, nullptr);
    self->impl->focus_in("?");
}

static void telexiva_engine_focus_in_id(IBusEngine* engine, const gchar* /*object_path*/, const gchar* client) {
    TelexivaEngine* self = TELEXIVA_ENGINE(engine);
    ibus_engine_get_surrounding_text(engine, nullptr, nullptr, nullptr);
    self->impl->focus_in(client != nullptr ? client : "-");
}

static void telexiva_engine_focus_out(IBusEngine* engine) { TELEXIVA_ENGINE(engine)->impl->focus_out(); }

static void telexiva_engine_focus_out_id(IBusEngine* engine, const gchar* /*object_path*/) {
    TELEXIVA_ENGINE(engine)->impl->focus_out();
}

static void telexiva_engine_reset(IBusEngine* engine) { TELEXIVA_ENGINE(engine)->impl->reset(); }

static void telexiva_engine_enable(IBusEngine* engine) {
    ibus_engine_get_surrounding_text(engine, nullptr, nullptr, nullptr);
}

static void telexiva_engine_set_capabilities(IBusEngine* engine, guint caps) {
    TELEXIVA_ENGINE(engine)->impl->set_capabilities((caps & IBUS_CAP_SURROUNDING_TEXT) != 0);
}

static void telexiva_engine_set_content_type(IBusEngine* engine, guint purpose, guint hints) {
    TELEXIVA_ENGINE(engine)->impl->set_content_type(to_purpose(purpose), hints);
}

static void telexiva_engine_set_surrounding_text(IBusEngine* engine, IBusText* text, guint cursor, guint anchor) {
    // Gọi lớp cha để IBus lưu surrounding text (cho get_surrounding_text).
    IBUS_ENGINE_CLASS(telexiva_engine_parent_class)->set_surrounding_text(engine, text, cursor, anchor);
    TELEXIVA_ENGINE(engine)->impl->on_surrounding_changed();
}

static void telexiva_engine_class_init(TelexivaEngineClass* klass) {
    IBUS_OBJECT_CLASS(klass)->destroy = telexiva_engine_destroy;
    IBusEngineClass* e = IBUS_ENGINE_CLASS(klass);
    e->process_key_event = telexiva_engine_process_key_event;
    e->focus_in = telexiva_engine_focus_in;
    e->focus_out = telexiva_engine_focus_out;
    e->focus_in_id = telexiva_engine_focus_in_id;
    e->focus_out_id = telexiva_engine_focus_out_id;
    e->reset = telexiva_engine_reset;
    e->enable = telexiva_engine_enable;
    e->set_capabilities = telexiva_engine_set_capabilities;
    e->set_content_type = telexiva_engine_set_content_type;
    e->set_surrounding_text = telexiva_engine_set_surrounding_text;
}

// ---------------------------------------------------------------------------
// main
// ---------------------------------------------------------------------------

namespace {

int engine_counter = 0;

IBusEngine* create_engine(IBusFactory* /*factory*/, const gchar* name, gpointer user_data) {
    auto* bus = static_cast<IBusBus*>(user_data);
    const std::string path = "/org/freedesktop/IBus/Engine/Telexiva/" + std::to_string(++engine_counter);
    // has-focus-id: IBus gọi focus_in_id kèm tên client.
    return IBUS_ENGINE(g_object_new(telexiva_engine_get_type(), "engine-name", name, "object-path", path.c_str(),
                                    "connection", ibus_bus_get_connection(bus), "has-focus-id", TRUE, nullptr));
}

void on_disconnected(IBusBus* /*bus*/, gpointer /*data*/) { ibus_quit(); }

}  // namespace

int main(int argc, char** argv) {
    const bool launched_by_ibus = argc > 1 && std::string(argv[1]) == "--ibus";
    ibus_init();
    IBusBus* bus = ibus_bus_new();
    if (!ibus_bus_is_connected(bus)) {
        std::fprintf(stderr, "Không kết nối được IBus daemon\n");
        return 1;
    }
    g_signal_connect(bus, "disconnected", G_CALLBACK(on_disconnected), nullptr);

    IBusFactory* factory = ibus_factory_new(ibus_bus_get_connection(bus));
    ibus_factory_add_engine(factory, kEngineName, telexiva_engine_get_type());
    g_signal_connect(factory, "create-engine", G_CALLBACK(create_engine), bus);

    if (launched_by_ibus) {
        ibus_bus_request_name(bus, kBusName, 0);
    } else {
        IBusComponent* component = ibus_component_new(kBusName, "Telexiva", "0.1.0", "GPL-3.0-or-later",
                                                      "phuocdon25", "https://github.com/phuocdon25/ibus-telexiva",
                                                      "", "telexiva");
        ibus_component_add_engine(component, ibus_engine_desc_new(kEngineName, "Telexiva (C++)", "Telexiva",
                                                                  "vi", "GPL-3.0-or-later", "phuocdon25", "", "us"));
        ibus_bus_register_component(bus, component);
    }
    file_log().write(std::string("started ibus=") + (launched_by_ibus ? "1" : "0") +
                     " english_words=" + std::to_string(english().size()));
    ibus_main();
    return 0;
}
