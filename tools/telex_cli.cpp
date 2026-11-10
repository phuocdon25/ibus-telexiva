// SPDX-License-Identifier: GPL-3.0-or-later
//
// telexiva-telex: đọc mỗi dòng một chuỗi phím từ stdin, in kết quả của core.
// Dùng cho tests/parity (so với prototype Python) và để thử nhanh:
//
//   echo vieejt | build/telexiva-telex
//   -> vieejt<TAB>việt<TAB>việt<TAB>việt<TAB>việt
//
// Cột: keys, transform(cũ), finalize(cũ), transform(mới), finalize(mới).
#include <iostream>
#include <string>

#include "telexiva/telex.hpp"

int main(int argc, char** argv) {
    bool no_dict = false;
    for (int i = 1; i < argc; ++i) {
        if (std::string(argv[i]) == "--no-dict") {
            no_dict = true;
        }
    }
    const telexiva::WordSet english = no_dict ? telexiva::WordSet{} : telexiva::WordSet::load_default();
    const telexiva::TelexOptions old_style{false, &english};
    const telexiva::TelexOptions new_style{true, &english};

    std::ios::sync_with_stdio(false);
    std::string keys;
    while (std::getline(std::cin, keys)) {
        std::cout << keys << '\t' << telexiva::transform(keys, old_style) << '\t'
                  << telexiva::finalize(keys, old_style) << '\t' << telexiva::transform(keys, new_style)
                  << '\t' << telexiva::finalize(keys, new_style) << '\n';
    }
    return 0;
}
