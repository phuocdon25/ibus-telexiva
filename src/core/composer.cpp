// SPDX-License-Identifier: GPL-3.0-or-later
#include "telexiva/composer.hpp"

#include <algorithm>
#include <cctype>
#include <fstream>

namespace telexiva {

namespace {

// Ký tự đứng ngay trước từ khiến từ đó được coi là code/URL/email (FR-013).
bool is_code_prev_char(char32_t c) {
    switch (c) {
        case U'_': case U'.': case U'/': case U'@': case U':': case U'\\':
        case U'$': case U'#': case U'=': case U'~': case U'<': case U'>':
            return true;
        default:
            return false;
    }
}

}  // namespace

std::u32string utf8_to_u32(const std::string& s) {
    std::u32string out;
    out.reserve(s.size());
    for (std::size_t i = 0; i < s.size();) {
        const auto b = static_cast<unsigned char>(s[i]);
        char32_t c = 0;
        std::size_t n = 0;
        if (b < 0x80) {
            c = b;
            n = 1;
        } else if ((b >> 5) == 0x6) {
            c = b & 0x1F;
            n = 2;
        } else if ((b >> 4) == 0xE) {
            c = b & 0x0F;
            n = 3;
        } else if ((b >> 3) == 0x1E) {
            c = b & 0x07;
            n = 4;
        } else {
            out.push_back(U'�');  // byte lỗi: thay bằng ký tự thay thế
            ++i;
            continue;
        }
        if (i + n > s.size()) {
            out.push_back(U'�');
            break;
        }
        for (std::size_t k = 1; k < n; ++k) {
            c = (c << 6) | (static_cast<unsigned char>(s[i + k]) & 0x3F);
        }
        out.push_back(c);
        i += n;
    }
    return out;
}

std::string u32_to_utf8(const std::u32string& s) {
    std::string out;
    out.reserve(s.size() * 2);
    for (char32_t c : s) {
        if (c < 0x80) {
            out.push_back(static_cast<char>(c));
        } else if (c < 0x800) {
            out.push_back(static_cast<char>(0xC0 | (c >> 6)));
            out.push_back(static_cast<char>(0x80 | (c & 0x3F)));
        } else if (c < 0x10000) {
            out.push_back(static_cast<char>(0xE0 | (c >> 12)));
            out.push_back(static_cast<char>(0x80 | ((c >> 6) & 0x3F)));
            out.push_back(static_cast<char>(0x80 | (c & 0x3F)));
        } else {
            out.push_back(static_cast<char>(0xF0 | (c >> 18)));
            out.push_back(static_cast<char>(0x80 | ((c >> 12) & 0x3F)));
            out.push_back(static_cast<char>(0x80 | ((c >> 6) & 0x3F)));
            out.push_back(static_cast<char>(0x80 | (c & 0x3F)));
        }
    }
    return out;
}

MacroTable MacroTable::load(const std::string& path) {
    MacroTable t;
    std::ifstream in(path);
    std::string line;
    while (std::getline(in, line)) {
        if (line.empty() || line[0] == '#') {
            continue;
        }
        const auto eq = line.find('=');
        if (eq == std::string::npos) {
            continue;
        }
        auto trim = [](const std::string& s) {
            const auto b = s.find_first_not_of(" \t");
            const auto e = s.find_last_not_of(" \t\r");
            return b == std::string::npos ? std::string() : s.substr(b, e - b + 1);
        };
        std::string key = trim(line.substr(0, eq));
        const std::string value = trim(line.substr(eq + 1));
        if (key.empty() || value.empty() ||
            !std::all_of(key.begin(), key.end(), [](char c) { return std::isalpha(static_cast<unsigned char>(c)); })) {
            continue;  // khóa phải là chữ cái ASCII (đúng chuỗi phím gõ ra)
        }
        for (char& c : key) {
            c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
        }
        t.add(std::move(key), utf8_to_u32(value));
    }
    return t;
}

void MacroTable::add(std::string key, std::u32string expansion) { table_[std::move(key)] = std::move(expansion); }

const std::u32string* MacroTable::find(std::string_view key_lower) const {
    const auto it = table_.find(std::string(key_lower));
    return it == table_.end() ? nullptr : &it->second;
}

EditAction Composer::restore_raw() {
    const std::u32string raw32 = utf8_to_u32(raw_);
    EditAction a = shown_ == raw32 ? EditAction::pass_through() : diff_to(raw32);
    frozen_ = true;
    return a;
}

EditAction Composer::diff_to(const std::u32string& next) {
    std::size_t p = 0;
    while (p < shown_.size() && p < next.size() && shown_[p] == next[p]) {
        ++p;
    }
    EditAction a = EditAction::replace(shown_.size() - p, u32_to_utf8(next.substr(p)));
    shown_ = next;
    return a;
}

EditAction Composer::letter(char key) {
    if (raw_.empty() && !frozen_ && is_code_prev_char(prev_char_)) {
        frozen_ = true;  // foo_bar, api/test, $var…
    }
    if (frozen_) {
        return EditAction::pass_through();
    }
    std::string raw = raw_ + key;
    const std::u32string next = utf8_to_u32(transform(raw, options_));
    std::u32string expected = shown_;
    expected.push_back(static_cast<unsigned char>(key));
    raw_ = std::move(raw);
    if (next == expected) {
        shown_ = next;  // không biến đổi: để ứng dụng tự chèn phím
        return EditAction::pass_through();
    }
    return diff_to(next);
}

WordEndResult Composer::word_end(char32_t ch) {
    WordEndResult r;
    if (!raw_.empty() && !frozen_) {
        if (ch == U'@') {
            // Phần trước @ của email không bao giờ có dấu: test@ -> giữ "test".
            const std::u32string raw32 = utf8_to_u32(raw_);
            if (shown_ != raw32) {
                r.fix = diff_to(raw32);
            }
        } else if (const std::u32string* exp = macro_for_raw(); exp != nullptr) {
            r.fix = diff_to(*exp);  // gõ tắt: ko -> không
        } else {
            const std::u32string final32 = utf8_to_u32(finalize(raw_, options_));
            if (final32 != shown_) {
                r.fix = diff_to(final32);  // khôi phục chính tả (text, class…)
            }
        }
    }
    raw_.clear();
    shown_.clear();
    frozen_ = false;
    prev_char_ = ch;
    return r;
}

bool Composer::attach(const std::u32string& word) {
    if (word.empty()) {
        return false;
    }
    const auto keys = keys_for(word);
    if (!keys || utf8_to_u32(transform(*keys, options_)) != word) {
        return false;
    }
    raw_ = *keys;
    shown_ = word;
    frozen_ = false;
    return true;
}

const std::u32string* Composer::macro_for_raw() {
    if (macros_ == nullptr || raw_.empty()) {
        return nullptr;
    }
    std::string lower = raw_;
    for (char& c : lower) {
        c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    }
    const std::u32string* exp = macros_->find(lower);
    if (exp == nullptr) {
        return nullptr;
    }
    // Giữ kiểu chữ: ko -> không, Ko -> Không, KO -> KHÔNG.
    const bool all_upper = raw_.size() >= 2 && std::all_of(raw_.begin(), raw_.end(), [](char c) {
                               return std::isupper(static_cast<unsigned char>(c)) != 0;
                           });
    macro_cased_ = all_upper ? to_upper(*exp) : *exp;
    if (!all_upper && std::isupper(static_cast<unsigned char>(raw_[0])) && !macro_cased_.empty()) {
        macro_cased_[0] = to_upper(macro_cased_.substr(0, 1))[0];
    }
    return &macro_cased_;
}

void Composer::reset() {
    raw_.clear();
    shown_.clear();
    frozen_ = false;
    prev_char_ = 0;
}

}  // namespace telexiva
