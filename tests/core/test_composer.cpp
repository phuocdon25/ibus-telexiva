// SPDX-License-Identifier: GPL-3.0-or-later
#include <catch2/catch_test_macros.hpp>

#include <algorithm>
#include <cctype>
#include <random>
#include <string>

#include "telexiva/composer.hpp"

using telexiva::Composer;
using telexiva::EditAction;

namespace {

bool is_letter_key(char c) {
    return std::isalpha(static_cast<unsigned char>(c)) != 0 || c == '[' || c == ']' || c == '{' ||
           c == '}';
}

// Ô nhập giả: áp dụng EditAction như engine sẽ làm với S2.
struct Field {
    Composer composer;
    std::u32string buf;
    std::size_t pass_through = 0;

    void apply(const EditAction& a) {
        if (a.kind == EditAction::Kind::Replace) {
            REQUIRE(a.delete_count <= buf.size());  // không bao giờ xóa quá phần đã có
            buf.resize(buf.size() - a.delete_count);
            buf += telexiva::utf8_to_u32(a.insert);
        }
    }

    Field& type(const std::string& keys) {
        for (char c : keys) {
            if (is_letter_key(c)) {
                const auto a = composer.letter(c);
                if (a.kind == EditAction::Kind::PassThrough) {
                    ++pass_through;
                    buf.push_back(static_cast<unsigned char>(c));
                } else {
                    apply(a);
                }
            } else {
                apply(composer.word_end(static_cast<unsigned char>(c)).fix);
                ++pass_through;
                buf.push_back(static_cast<unsigned char>(c));
            }
        }
        return *this;
    }

    [[nodiscard]] std::string text() const { return telexiva::u32_to_utf8(buf); }
};

}  // namespace

TEST_CASE("Composer: câu tiếng Việt", "[composer]") {
    CHECK(Field{}.type("Vieejt Nam ddepj quas ").text() == "Việt Nam đẹp quá ");
    CHECK(Field{}.type("dudocwj chuaw tassk ").text() == "được chưa task ");
}

TEST_CASE("Composer: pass-through first (BUG-001, BUG-003)", "[composer]") {
    Field digits;
    digits.type("1200000");
    CHECK(digits.text() == "1200000");
    CHECK(digits.pass_through == 7);

    Field lo;
    lo.type("lo");
    CHECK(lo.pass_through == 2);
}

TEST_CASE("Composer: khôi phục từ tiếng Anh khi kết thúc từ", "[composer]") {
    CHECK(Field{}.type("const text = function return ").text() == "const text = function return ");
}

TEST_CASE("Composer: ngữ cảnh code, URL, email (FR-013)", "[composer]") {
    for (const char* s : {"foo_bar-baz ", "api/test ", "obj.test ", "$var ", "a=test ", "test@example.com "}) {
        INFO(s);
        CHECK(Field{}.type(s).text() == s);
    }
    CHECK(Field{}.type("xong. Tieeps tucj, nhes! ").text() == "xong. Tiếp tục, nhé! ");
}

TEST_CASE("Composer: freeze và reset", "[composer]") {
    Field f;
    f.type("vie");
    f.composer.freeze();          // engine: guard chặn
    f.type("ej ");
    CHECK(f.text() == "vieej ");  // phần còn lại của từ đi thẳng
    f.type("vieejt ");
    CHECK(f.text() == "vieej việt ");  // từ sau bình thường
}

TEST_CASE("Composer: fuzz — không crash, UTF-8 hợp lệ, không xóa quá nội dung", "[composer][fuzz]") {
    std::mt19937 rng(20261111);
    const std::string alphabet = "aeiouydwsfrxjzqcgnhtmplbkv[]{} .,_@/1AEOUDW";
    std::uniform_int_distribution<std::size_t> pick(0, alphabet.size() - 1);
    std::uniform_int_distribution<int> len(1, 40);
    for (int iter = 0; iter < 50000; ++iter) {
        std::string keys;
        const int n = len(rng);
        for (int i = 0; i < n; ++i) {
            keys.push_back(alphabet[pick(rng)]);
        }
        Field f;
        f.type(keys);  // REQUIRE trong apply: không xóa quá nội dung
        const std::string out = f.text();
        // Round-trip UTF-8 phải ổn định và không có ký tự thay thế (byte lỗi).
        const auto decoded = telexiva::utf8_to_u32(out);
        REQUIRE(telexiva::u32_to_utf8(decoded) == out);
        REQUIRE(std::find(decoded.begin(), decoded.end(), U'�') == decoded.end());
    }
}
