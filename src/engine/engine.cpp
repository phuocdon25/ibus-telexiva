// SPDX-License-Identifier: GPL-3.0-or-later
#include "telexiva/engine.hpp"

#include <algorithm>
#include <cstdio>

namespace telexiva {

namespace {

constexpr std::uint32_t kKeyvalBackSpace = 0xff08;  // X keysym
constexpr std::uint32_t kKeycodeBackSpace = 14;     // evdev
constexpr std::uint32_t kReleaseMask = 1u << 30;    // IBUS_RELEASE_MASK

bool ends_with(const std::u32string& s, const std::u32string& suffix) {
    return s.size() >= suffix.size() && s.compare(s.size() - suffix.size(), suffix.size(), suffix) == 0;
}

std::size_t utf8_size(const std::u32string& s) { return u32_to_utf8(s).size(); }

std::string fmt(const char* format, double a = 0, double b = 0, double c = 0, double d = 0) {
    char buf[256];
    std::snprintf(buf, sizeof buf, format, a, b, c, d);
    return buf;
}

const char* strategy_name(Strategy s) {
    switch (s) {
        case Strategy::Preedit: return "s1";
        case Strategy::Surrounding: return "s2";
        case Strategy::ForwardKeys: return "s3";
        default: return "auto";
    }
}

}  // namespace

Engine::Engine(Host& host, EngineConfig config)
    : host_(host), config_(config), composer_(config.telex) {}

void Engine::log(const std::string& line) { host_.log("[" + client_ + "] " + line); }

Strategy Engine::effective_strategy() const {
    if (config_.strategy != Strategy::Auto) {
        return config_.strategy;
    }
    if (preedit_mode_) {
        return Strategy::Preedit;
    }
    if (purpose_ == Purpose::Terminal) {
        return Strategy::ForwardKeys;
    }
    return has_surrounding_ ? Strategy::Surrounding : Strategy::ForwardKeys;
}

// ---------------------------------------------------------------------------
// Phím
// ---------------------------------------------------------------------------

bool Engine::process_key(const Key& key) {
    if (waiting_) {
        // Phím đến trong lúc đang đợi xác nhận: giữ lại, xử lý sau đúng thứ tự.
        if (key.release) {
            return !queue_.empty();
        }
        queue_.push_back(key);
        return true;
    }
    const bool handled = handle(key);
    drain_queue();
    return handled;
}

void Engine::drain_queue() {
    while (!queue_.empty()) {
        const Key key = queue_.front();
        queue_.pop_front();
        if (handle(key)) {
            continue;
        }
        // Phím lẽ ra đi thẳng nhưng đã bị giữ lại: chèn bằng commit (chữ, số, dấu câu).
        if ((key.kind == Key::Kind::Letter || key.kind == Key::Kind::Printable) && !key.shortcut) {
            host_.commit(u32_to_utf8(std::u32string(1, key.ch)));
            log("queued key replayed via commit");
        } else {
            host_.forward_key(key.keyval, key.keycode, key.state);
            log("queued key replayed via forward");
        }
    }
}

bool Engine::handle(const Key& key) {
    if (key.release || key.kind == Key::Kind::Modifier) {
        return false;
    }
    if (purpose_ == Purpose::Password || purpose_ == Purpose::Pin) {
        return false;  // FR-011
    }
    if (key.shortcut) {
        if (preedit_mode_ && !preedit_raw_.empty()) {
            commit_preedit(true);
        }
        reset_word("shortcut");
        return false;
    }
    const bool is_letter = key.kind == Key::Kind::Letter;

    if (pending_) {
        check_pending_verify();
    }
    // Ngữ cảnh code (FR-013): nếu không biết ký tự trước từ (sau khi click), đọc từ ô nhập.
    if (is_letter && composer_.raw().empty() && !composer_.frozen() && composer_.prev_char() == 0 &&
        has_surrounding_) {
        const Surrounding s = host_.surrounding();
        if (s.cursor > 0 && s.cursor <= s.text.size()) {
            composer_.set_prev_char(s.text[s.cursor - 1]);
        }
    }

    if (effective_strategy() == Strategy::Preedit) {
        return process_preedit(key);
    }

    if (!is_letter) {
        if (key.kind == Key::Kind::Printable || key.kind == Key::Kind::Enter || key.kind == Key::Kind::Tab) {
            const std::u32string old = composer_.shown();
            const char32_t c = key.kind == Key::Kind::Printable ? key.ch : 0;
            const WordEndResult r = composer_.word_end(c);
            if (r.fix.kind == EditAction::Kind::Replace) {
                log(c == U'@' ? "email_local_part -> restore raw" : "finalize restore");
                apply_edit(old, r.fix);
            }
        } else {
            composer_.reset();
        }
        recent_.clear();
        inflight_.reset();
        return false;  // phím đi thẳng tới ứng dụng
    }

    const std::u32string old = composer_.shown();
    const bool was_frozen = composer_.frozen();
    const EditAction a = composer_.letter(static_cast<char>(key.ch));
    if (!was_frozen && composer_.frozen()) {
        log("code_context -> keep word");
    }
    if (a.kind == EditAction::Kind::PassThrough) {
        note_shown(old, composer_.shown());
        if (pending_ && !composer_.frozen()) {
            pending_->expect.push_back(key.ch);
            pending_->broken.push_back(key.ch);
            pending_->ins.push_back(key.ch);
        }
        return false;
    }
    if (apply_edit(old, a)) {
        return true;
    }
    // Guard chặn: không chắc nội dung ô nhập. Phần còn lại của từ đi thẳng.
    composer_.freeze();
    recent_.clear();
    inflight_.reset();
    return false;
}

void Engine::note_shown(const std::u32string& old, const std::u32string& now) {
    if (old != now) {
        recent_.push_back(old);
        if (recent_.size() > 2) {
            recent_.erase(recent_.begin());
        }
    }
}

void Engine::reset_word(const char* why) {
    if (!composer_.raw().empty()) {
        log(std::string("reset why=") + why);
    }
    composer_.reset();
    recent_.clear();
    inflight_.reset();
}

// ---------------------------------------------------------------------------
// Thực hiện một lần sửa (S2 / S3)
// ---------------------------------------------------------------------------

bool Engine::apply_edit(const std::u32string& old, const EditAction& action) {
    const std::u32string ins = utf8_to_u32(action.insert);
    std::size_t n_del = action.delete_count;
    const std::size_t p = old.size() - std::min(n_del, old.size());
    const std::u32string now = old.substr(0, p) + ins;
    const Strategy strategy = effective_strategy();

    if (n_del && strategy == Strategy::Surrounding) {
        wait_confirm();
    }
    if (n_del && !guard_ok(old)) {
        return false;
    }
    if (n_del) {
        inflight_ = std::make_pair(old.substr(0, p), host_.now_ms());
    }

    std::u32string to_delete = old.substr(p);
    if (n_del && strategy == Strategy::Surrounding && !ins.empty() && selection_after_cursor()) {
        // Thanh địa chỉ Chrome: gợi ý tự điền đang bôi đen sau con trỏ, Chrome bỏ qua lệnh
        // xóa khi có vùng chọn (gox -> "goõ"). Bước 1: commit, Chrome thay vùng chọn.
        // Bước 2: đợi xác nhận, rồi xóa (phần cũ + phần vừa chèn) và chèn lại.
        host_.commit(u32_to_utf8(ins));
        awaiting_confirm_ = host_.now_ms();
        wait_confirm();
        to_delete += ins;
        n_del = to_delete.size();
        log(fmt("selection_after_cursor -> two_phase del=%.0f", static_cast<double>(n_del)));
    }
    if (n_del) {
        if (strategy == Strategy::Surrounding) {
            const unsigned n = mutter_safe_delete_count(to_delete);
            host_.delete_surrounding(-static_cast<int>(n), n);
        } else {
            for (std::size_t i = 0; i < n_del; ++i) {
                host_.forward_key(kKeyvalBackSpace, kKeycodeBackSpace, 0);
                host_.forward_key(kKeyvalBackSpace, kKeycodeBackSpace, kReleaseMask);
            }
        }
    }
    if (!ins.empty()) {
        host_.commit(u32_to_utf8(ins));
    }
    note_shown(old, now);
    if (strategy == Strategy::Surrounding && n_del) {
        const double t = host_.now_ms();
        pending_ = PendingVerify{now, old + ins, ins, 3, t - last_edit_at_};
        last_edit_at_ = t;
        awaiting_confirm_ = t;
    }
    log(std::string("replace strategy=") + strategy_name(strategy) + " del=" + std::to_string(n_del) +
        " ins=" + std::to_string(ins.size()));
    return true;
}

bool Engine::guard_ok(const std::u32string& old) {
    if (!config_.guard || !has_surrounding_) {
        return true;
    }
    const Surrounding s = host_.surrounding();
    const std::uint32_t cursor = std::min<std::uint32_t>(s.cursor, static_cast<std::uint32_t>(s.text.size()));
    const std::uint32_t anchor = std::min<std::uint32_t>(s.anchor, static_cast<std::uint32_t>(s.text.size()));
    const std::u32string before = s.text.substr(0, cursor);

    std::vector<std::u32string> candidates;
    if (!old.empty()) {
        candidates.push_back(old);
    }
    for (const auto& r : recent_) {
        if (!r.empty()) {
            candidates.push_back(r);
        }
    }
    // Ngay sau một lần sửa, ô nhập có thể báo trạng thái "đã xóa, chưa chèn" (0,5 giây).
    if (inflight_ && host_.now_ms() - inflight_->second < 500 && !inflight_->first.empty()) {
        candidates.push_back(inflight_->first);
    }
    if (candidates.empty()) {
        candidates.emplace_back();
    }
    auto any_suffix = [&](const std::u32string& text) {
        return std::any_of(candidates.begin(), candidates.end(),
                           [&](const std::u32string& c) { return ends_with(text, c); });
    };
    // Vùng chọn SAU con trỏ (gợi ý tự điền) không ảnh hưởng.
    if (anchor >= cursor && any_suffix(before)) {
        return true;
    }
    if (anchor != cursor && any_suffix(s.text.substr(0, anchor))) {
        log(fmt("guard matched_by=anchor cursor=%.0f anchor=%.0f", cursor, anchor));
        return true;
    }
    log(fmt("guard mismatch before_len=%.0f cursor=%.0f anchor=%.0f shown_len=%.0f",
            static_cast<double>(before.size()), cursor, anchor, static_cast<double>(old.size())));
    return false;
}

unsigned Engine::mutter_safe_delete_count(const std::u32string& to_delete) {
    // Mutter đổi số KÝ TỰ sang số BYTE bằng bản sao surrounding text của nó. Khi bản sao
    // là một trạng thái cũ của từ, chọn số ký tự k sao cho k ký tự cuối của bản sao có
    // cùng số byte với phần cần xóa thật (gocs + o -> "gócốc" nếu không bù).
    const auto fallback = static_cast<unsigned>(to_delete.size());
    if (!has_surrounding_) {
        return fallback;
    }
    const Surrounding s = host_.surrounding();
    const std::u32string view = s.text.substr(0, std::min<std::size_t>(s.cursor, s.text.size()));
    if (ends_with(view, to_delete)) {
        return fallback;  // bản sao đã mới
    }
    if (inflight_ && !inflight_->first.empty() && ends_with(view, inflight_->first)) {
        return fallback;  // Mutter đang cập nhật dở ("đã xóa, chưa chèn")
    }
    if (std::none_of(recent_.begin(), recent_.end(),
                     [&](const std::u32string& r) { return !r.empty() && ends_with(view, r); })) {
        return fallback;  // không nhận ra bản sao
    }
    const std::size_t want = utf8_size(to_delete);
    std::size_t total = 0;
    for (std::size_t k = 1; k <= view.size(); ++k) {
        total += utf8_size(view.substr(view.size() - k, 1));
        if (total == want) {
            log(fmt("delete_byte_compensated chars=%.0f->%.0f bytes=%.0f",
                    static_cast<double>(to_delete.size()), static_cast<double>(k), static_cast<double>(want)));
            return static_cast<unsigned>(k);
        }
        if (total > want) {
            break;
        }
    }
    log("delete_byte_mismatch");
    return fallback;
}

bool Engine::selection_after_cursor() {
    if (!has_surrounding_) {
        return false;
    }
    const Surrounding s = host_.surrounding();
    return s.anchor > s.cursor;
}

void Engine::wait_confirm() {
    if (!awaiting_confirm_) {
        return;
    }
    const double start = host_.now_ms();
    if (start - *awaiting_confirm_ > 300) {
        awaiting_confirm_.reset();  // quá cũ: ô nhập không gửi xác nhận
        return;
    }
    waiting_ = true;
    while (awaiting_confirm_ && host_.now_ms() - start < config_.wait_ms) {
        host_.iterate_main_loop();
    }
    waiting_ = false;
    log(fmt("wait_confirm waited_ms=%.1f confirmed=%.0f queued=%.0f", host_.now_ms() - start,
            awaiting_confirm_ ? 0.0 : 1.0, static_cast<double>(queue_.size())));
    awaiting_confirm_.reset();
}

void Engine::on_surrounding_changed() {
    if (awaiting_confirm_) {
        log(fmt("confirm_ms=%.1f", host_.now_ms() - *awaiting_confirm_));
        awaiting_confirm_.reset();
    }
}

void Engine::check_pending_verify() {
    if (!pending_ || !has_surrounding_) {
        pending_.reset();
        return;
    }
    const Surrounding s = host_.surrounding();
    const std::u32string b1 = s.text.substr(0, std::min<std::size_t>(s.cursor, s.text.size()));
    const std::u32string b2 = s.text.substr(0, std::min<std::size_t>(s.anchor, s.text.size()));
    auto either = [&](const std::u32string& suffix) { return ends_with(b1, suffix) || ends_with(b2, suffix); };

    if (either(pending_->expect)) {
        pending_.reset();
        return;
    }
    if (awaiting_confirm_) {
        // Ô nhập chưa xác nhận: surrounding text có thể còn cũ, chưa kết luận được.
        if (--pending_->tries <= 0) {
            pending_.reset();
        }
        return;
    }
    const PendingVerify pv = *pending_;
    pending_.reset();
    if (!either(pv.ins)) {
        // Chữ engine vừa chèn không còn: trang tự thay nội dung (chọn gợi ý…). Không phải lỗi S2.
        log("content_changed_after_edit (keep S2)");
        reset_word("content_changed");
        return;
    }
    // Chữ engine chèn vẫn ở đó nhưng phần trước sai (taoạo, gống…): ô không đáng tin với S2.
    preedit_mode_ = true;
    log(std::string("s2_unreliable kind=") + (either(pv.broken) ? "ignored" : "mismatch") +
        " -> preedit purpose=" + std::to_string(static_cast<int>(purpose_)) + " hints=" + std::to_string(hints_));
    reset_word("s2_unreliable");
}

// ---------------------------------------------------------------------------
// Preedit (S1)
// ---------------------------------------------------------------------------

bool Engine::process_preedit(const Key& key) {
    if (key.kind == Key::Kind::Letter) {
        preedit_raw_.push_back(static_cast<char>(key.ch));
        show_preedit();
        return true;
    }
    if (key.kind == Key::Kind::Backspace && !preedit_raw_.empty()) {
        // Xóa một ký tự đang hiển thị, giữ dấu của phần còn lại (tạo -> tạ).
        const std::u32string target = preedit_shown_.substr(0, preedit_shown_.empty() ? 0 : preedit_shown_.size() - 1);
        std::string popped;
        while (!preedit_raw_.empty() &&
               utf8_to_u32(transform(preedit_raw_, config_.telex)).size() >= preedit_shown_.size()) {
            popped.insert(popped.begin(), preedit_raw_.back());
            preedit_raw_.pop_back();
        }
        for (char k : popped) {
            if (utf8_to_u32(transform(preedit_raw_ + k, config_.telex)) == target) {
                preedit_raw_ += k;
                break;
            }
        }
        if (preedit_raw_.empty()) {
            host_.hide_preedit();
            preedit_shown_.clear();
        } else {
            show_preedit();
        }
        return true;
    }
    commit_preedit(key.kind != Key::Kind::Escape);
    return false;
}

void Engine::show_preedit() {
    const std::string text = transform(preedit_raw_, config_.telex);
    host_.update_preedit(text);
    preedit_shown_ = utf8_to_u32(text);
}

void Engine::commit_preedit(bool final) {
    if (!preedit_raw_.empty()) {
        const std::string text =
            final ? finalize(preedit_raw_, config_.telex) : transform(preedit_raw_, config_.telex);
        host_.hide_preedit();
        host_.commit(text);
    }
    preedit_raw_.clear();
    preedit_shown_.clear();
}

// ---------------------------------------------------------------------------
// Sự kiện từ ứng dụng
// ---------------------------------------------------------------------------

void Engine::focus_in(const std::string& client) {
    client_ = client.empty() ? "-" : client;
    reset_word("focus_in");
    if (preedit_mode_) {
        log("preedit_mode off (focus changed)");
    }
    preedit_mode_ = false;  // ô mới: thử lại không nháp
    preedit_raw_.clear();
    preedit_shown_.clear();
    pending_.reset();
    log(fmt("focus_in surrounding=%.0f purpose=%.0f hints=%.0f", has_surrounding_ ? 1 : 0,
            static_cast<double>(purpose_), static_cast<double>(hints_)));
}

void Engine::focus_out() {
    reset_word("focus_out");
    preedit_raw_.clear();
    preedit_shown_.clear();
}

void Engine::reset() {
    reset_word("reset");
    preedit_raw_.clear();
    preedit_shown_.clear();
}

void Engine::set_capabilities(bool surrounding_text) { has_surrounding_ = surrounding_text; }

void Engine::set_content_type(Purpose purpose, std::uint32_t hints) {
    purpose_ = purpose;
    hints_ = hints;
}

}  // namespace telexiva
