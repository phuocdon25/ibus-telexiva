// SPDX-License-Identifier: GPL-3.0-or-later
//
// Telexiva core: quy tắc gõ Telex (FR-001).
//
// Hàm thuần, không phụ thuộc IBus hay GUI. Đầu vào là chuỗi phím ASCII của một từ,
// đầu ra là chữ UTF-8 (NFC). Hành vi bám theo prototype Python (prototype/telex.py),
// được kiểm tra tự động bằng tests/parity.
#pragma once

#include <cstddef>
#include <string>
#include <string_view>
#include <unordered_set>

namespace telexiva {

// Tập từ tiếng Anh (chữ thường, ASCII), dùng để phân biệt "error" (chữ đôi thật)
// với "tassk" (gõ lặp để hủy dấu) — xem FR-001 c).
class WordSet {
public:
    // Nạp từ file một từ mỗi dòng (ví dụ /usr/share/dict/words). Trả về tập rỗng nếu
    // không mở được file. Chỉ giữ từ ASCII, chuyển về chữ thường.
    static WordSet load(const std::string& path);
    // Thử lần lượt các đường dẫn từ điển mặc định trên Debian/Ubuntu.
    static WordSet load_default();

    void insert(std::string word);
    [[nodiscard]] bool contains(std::string_view word) const;
    [[nodiscard]] std::size_t size() const { return words_.size(); }

private:
    std::unordered_set<std::string> words_;
};

struct TelexOptions {
    bool new_style = false;             // đặt dấu kiểu mới (hoà) thay vì kiểu cũ (hòa)
    const WordSet* english = nullptr;   // tùy chọn; nullptr = hành vi như UniKey
};

// Chữ hiển thị trong lúc đang gõ (kiểm tra chính tả "lỏng": chuỗi chỉ cần có thể
// trở thành một âm tiết hợp lệ).
[[nodiscard]] std::string transform(std::string_view keys, const TelexOptions& options = {});

// Chữ cuối cùng khi kết thúc từ (kiểm tra chặt; sai chính tả thì trả lại nguyên
// chuỗi phím, ví dụ "text" -> "text").
[[nodiscard]] std::string finalize(std::string_view keys, const TelexOptions& options = {});

}  // namespace telexiva
