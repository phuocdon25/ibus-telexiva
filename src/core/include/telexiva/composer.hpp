// SPDX-License-Identifier: GPL-3.0-or-later
//
// Composer: theo dõi từ đang gõ trong MỘT ô nhập và quyết định mỗi phím cần làm gì
// (FR-009 "pass-through first", FR-013 ngữ cảnh code/URL/email).
//
// Composer không biết gì về IBus hay ứng dụng: nó chỉ trả về EditAction. Engine
// (Phase 2) chịu trách nhiệm thực hiện EditAction bằng S2 (delete_surrounding_text +
// commit) hoặc preedit, kiểm tra guard, đợi xác nhận…
//
// Hành vi bám theo prototype/telexiva_proto.py (phần không phụ thuộc ứng dụng),
// được kiểm tra bằng tests/parity (mode --compose).
#pragma once

#include <cstddef>
#include <string>
#include <utility>

#include "telexiva/telex.hpp"

namespace telexiva {

struct EditAction {
    enum class Kind {
        PassThrough,  // để phím đi thẳng tới ứng dụng, như khi gõ English
        Replace,      // xóa `delete_count` ký tự trước con trỏ, rồi chèn `insert`
        Consumed,     // phím đã được xử lý (Replace không cần ghi gì thêm)
    };
    Kind kind = Kind::PassThrough;
    std::size_t delete_count = 0;  // tính theo ký tự Unicode (code point)
    std::string insert;            // UTF-8

    static EditAction pass_through() { return EditAction{}; }
    static EditAction replace(std::size_t del, std::string ins) {
        EditAction a;
        a.kind = Kind::Replace;
        a.delete_count = del;
        a.insert = std::move(ins);
        return a;
    }
    bool operator==(const EditAction&) const = default;
};

// Kết quả của một phím không phải chữ cái (space, dấu câu, số…): có thể cần sửa từ
// vừa kết thúc trước (khôi phục chính tả, phần trước @ của email), rồi phím vẫn đi thẳng.
struct WordEndResult {
    EditAction fix;  // PassThrough nếu không cần sửa
};

class Composer {
public:
    Composer() = default;
    explicit Composer(TelexOptions options) : options_(options) {}

    // Chữ cái ASCII hoặc [ ] { }.
    EditAction letter(char key);

    // Phím in được không phải chữ cái (space, dấu câu, số, @…), hoặc Enter/Tab.
    // Kết thúc từ hiện tại; phím luôn đi thẳng sau khi áp dụng `fix`.
    WordEndResult word_end(char32_t ch);

    // Phím điều hướng, click, đổi focus, phím tắt…: bỏ từ hiện tại, không sửa gì.
    void reset();

    // Engine báo không chắc nội dung ô nhập (guard chặn): các chữ còn lại của từ đi thẳng.
    void freeze() { frozen_ = true; }

    // Engine báo ký tự ngay trước con trỏ khi Composer không tự biết (sau khi click):
    // dùng cho ngữ cảnh code (FR-013).
    void set_prev_char(char32_t c) { prev_char_ = c; }

    [[nodiscard]] const std::string& raw() const { return raw_; }
    [[nodiscard]] const std::u32string& shown() const { return shown_; }
    [[nodiscard]] bool frozen() const { return frozen_; }
    [[nodiscard]] char32_t prev_char() const { return prev_char_; }

private:
    EditAction diff_to(const std::u32string& next);

    TelexOptions options_;
    std::string raw_;          // các phím của từ hiện tại
    std::u32string shown_;     // chữ Composer tin là đang nằm trong ứng dụng cho từ này
    bool frozen_ = false;      // ngữ cảnh code hoặc guard: phần còn lại của từ đi thẳng
    char32_t prev_char_ = 0;   // ký tự không phải chữ gần nhất (0 = không biết)
};

// Tiện ích UTF-8 dùng chung cho engine và test.
std::u32string utf8_to_u32(const std::string& s);
std::string u32_to_utf8(const std::u32string& s);

}  // namespace telexiva
