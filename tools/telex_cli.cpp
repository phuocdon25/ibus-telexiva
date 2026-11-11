// SPDX-License-Identifier: GPL-3.0-or-later
//
// telexiva-telex: đọc mỗi dòng một chuỗi phím từ stdin, in kết quả của core.
// Dùng cho tests/parity (so với prototype Python) và để thử nhanh:
//
//   echo vieejt | build/telexiva-telex
//   -> vieejt<TAB>việt<TAB>việt<TAB>việt<TAB>việt
//
// Cột: keys, transform(cũ), finalize(cũ), transform(mới), finalize(mới).
//
// Chế độ --compose: mỗi dòng là chuỗi phím của cả câu (chữ, dấu cách, dấu câu…);
// mô phỏng một ô nhập áp dụng EditAction của Composer và in nội dung cuối cùng.
//
//   echo "Vieejt Nam, foo_bar test@x.com " | build/telexiva-telex --compose
#include <algorithm>
#include <cctype>
#include <iostream>
#include <string>

#include "telexiva/composer.hpp"
#include "telexiva/telex.hpp"

namespace {

bool is_letter_key(char c) {
    return std::isalpha(static_cast<unsigned char>(c)) != 0 || c == '[' || c == ']' || c == '{' ||
           c == '}';
}

void apply_action(std::u32string& buf, const telexiva::EditAction& a) {
    if (a.kind == telexiva::EditAction::Kind::Replace) {
        buf.resize(buf.size() - std::min(a.delete_count, buf.size()));
        buf += telexiva::utf8_to_u32(a.insert);
    }
}

std::string compose(const std::string& keys, const telexiva::TelexOptions& opt) {
    telexiva::Composer composer(opt);
    std::u32string buf;
    for (char c : keys) {
        if (is_letter_key(c)) {
            const auto a = composer.letter(c);
            if (a.kind == telexiva::EditAction::Kind::PassThrough) {
                buf.push_back(static_cast<unsigned char>(c));
            } else {
                apply_action(buf, a);
            }
        } else {
            apply_action(buf, composer.word_end(static_cast<unsigned char>(c)).fix);
            buf.push_back(static_cast<unsigned char>(c));
        }
    }
    return telexiva::u32_to_utf8(buf);
}

}  // namespace

int main(int argc, char** argv) {
    bool no_dict = false;
    bool compose_mode = false;
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--no-dict") {
            no_dict = true;
        } else if (arg == "--compose") {
            compose_mode = true;
        }
    }
    const telexiva::WordSet english = no_dict ? telexiva::WordSet{} : telexiva::WordSet::load_default();
    const telexiva::TelexOptions old_style{false, &english};
    const telexiva::TelexOptions new_style{true, &english};

    std::ios::sync_with_stdio(false);
    std::string keys;
    while (std::getline(std::cin, keys)) {
        if (compose_mode) {
            std::cout << keys << '\t' << compose(keys, old_style) << '\n';
            continue;
        }
        std::cout << keys << '\t' << telexiva::transform(keys, old_style) << '\t'
                  << telexiva::finalize(keys, old_style) << '\t' << telexiva::transform(keys, new_style)
                  << '\t' << telexiva::finalize(keys, new_style) << '\n';
    }
    return 0;
}
