// SPDX-License-Identifier: GPL-3.0-or-later
//
// Chuyển từ prototype/telex.py. Giữ cấu trúc và tên hàm tương ứng để dễ đối chiếu;
// mọi khác biệt hành vi sẽ bị tests/parity bắt được.
#include "telexiva/telex.hpp"

#include <algorithm>
#include <array>
#include <cctype>
#include <fstream>
#include <optional>
#include <set>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace telexiva {
namespace {

using u32 = std::u32string;
using U32Set = std::unordered_set<u32>;

// ---------------------------------------------------------------------------
// UTF-8
// ---------------------------------------------------------------------------

void append_utf8(std::string& out, char32_t c) {
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

std::string to_utf8(const u32& s) {
    std::string out;
    out.reserve(s.size() * 2);
    for (char32_t c : s) {
        append_utf8(out, c);
    }
    return out;
}

// ---------------------------------------------------------------------------
// Bảng dữ liệu tiếng Việt
// ---------------------------------------------------------------------------

struct Tables {
    // Mỗi nguyên âm -> 6 dạng: không dấu, sắc, huyền, hỏi, ngã, nặng.
    std::unordered_map<char32_t, u32> toned;
    std::unordered_set<char32_t> vowels;
    std::unordered_map<char32_t, char32_t> base;  // ă/â -> a, ê -> e, ô/ơ -> o, ư -> u
    std::unordered_set<char32_t> horn_diacritics;
    std::unordered_map<char32_t, char32_t> upper;
    std::vector<u32> initials;  // dài trước, ngắn sau
    U32Set finals, final_prefixes, stop_finals;
    U32Set nuclei, open_only, nucleus_base_prefixes, closable_bases, nucleus_prefixes;

    [[nodiscard]] u32 strip(const u32& s) const {
        u32 out = s;
        for (char32_t& c : out) {
            if (auto it = base.find(c); it != base.end()) {
                c = it->second;
            }
        }
        return out;
    }
    [[nodiscard]] bool is_vowel(char32_t c) const { return vowels.count(c) != 0; }
};

const Tables& tables() {
    static const Tables instance = [] {
        Tables t;
        const std::array<u32, 12> toned = {
            U"aáàảãạ", U"ăắằẳẵặ", U"âấầẩẫậ", U"eéèẻẽẹ", U"êếềểễệ", U"iíìỉĩị",
            U"oóòỏõọ", U"ôốồổỗộ", U"ơớờởỡợ", U"uúùủũụ", U"ưứừửữự", U"yýỳỷỹỵ",
        };
        const std::array<u32, 12> toned_upper = {
            U"AÁÀẢÃẠ", U"ĂẮẰẲẴẶ", U"ÂẤẦẨẪẬ", U"EÉÈẺẼẸ", U"ÊẾỀỂỄỆ", U"IÍÌỈĨỊ",
            U"OÓÒỎÕỌ", U"ÔỐỒỔỖỘ", U"ƠỚỜỞỠỢ", U"UÚÙỦŨỤ", U"ƯỨỪỬỮỰ", U"YÝỲỶỸỴ",
        };
        for (std::size_t i = 0; i < toned.size(); ++i) {
            t.toned[toned[i][0]] = toned[i];
            t.vowels.insert(toned[i][0]);
            for (std::size_t j = 0; j < toned[i].size(); ++j) {
                t.upper[toned[i][j]] = toned_upper[i][j];
            }
        }
        t.upper[U'đ'] = U'Đ';
        t.base = {{U'ă', U'a'}, {U'â', U'a'}, {U'ê', U'e'}, {U'ô', U'o'}, {U'ơ', U'o'}, {U'ư', U'u'}};
        t.horn_diacritics = {U'â', U'ă', U'ê', U'ô', U'ơ', U'ư'};

        t.initials = {U"ngh", U"ng", U"nh", U"ch", U"gh", U"gi", U"kh", U"ph", U"qu", U"th", U"tr",
                      U"b",   U"c",  U"d",  U"đ",  U"g",  U"h",  U"k",  U"l",  U"m",  U"n",  U"p",
                      U"r",   U"s",  U"t",  U"v",  U"x"};
        std::stable_sort(t.initials.begin(), t.initials.end(),
                         [](const u32& a, const u32& b) { return a.size() > b.size(); });

        t.finals = {U"c", U"ch", U"m", U"n", U"ng", U"nh", U"p", U"t"};
        for (const u32& f : t.finals) {
            for (std::size_t i = 0; i <= f.size(); ++i) {
                t.final_prefixes.insert(f.substr(0, i));
            }
        }
        t.stop_finals = {U"c", U"ch", U"p", U"t"};

        t.nuclei = {U"a",   U"ă",   U"â",   U"e",   U"ê",   U"i",   U"o",   U"ô",   U"ơ",
                    U"u",   U"ư",   U"y",   U"ai",  U"ao",  U"au",  U"ay",  U"âu",  U"ây",
                    U"eo",  U"êu",  U"ia",  U"iê",  U"iu",  U"oa",  U"oă",  U"oe",  U"oi",
                    U"ôi",  U"ơi",  U"oo",  U"ua",  U"uâ",  U"uê",  U"ui",  U"uô",  U"uơ",
                    U"uy",  U"ưa",  U"ưi",  U"ưu",  U"ươ",  U"yê",  U"iêu", U"yêu", U"oai",
                    U"oay", U"oeo", U"uây", U"uôi", U"uya", U"uyê", U"uyu", U"ươi", U"ươu"};
        // Vần mở: không được có phụ âm cuối.
        t.open_only = {U"ai",  U"ao",  U"au",  U"ay",  U"âu",  U"ây",  U"eo",  U"êu",
                       U"ia",  U"iu",  U"oi",  U"ôi",  U"ơi",  U"ua",  U"ui",  U"ưa",
                       U"ưi",  U"ưu",  U"iêu", U"yêu", U"oai", U"oay", U"oeo", U"uây",
                       U"uôi", U"uya", U"uyu", U"ươi", U"ươu", U"uơ"};
        for (const u32& n : t.nuclei) {
            const u32 stripped = t.strip(n);
            for (std::size_t i = 0; i <= n.size(); ++i) {
                t.nucleus_base_prefixes.insert(stripped.substr(0, i));
                t.nucleus_prefixes.insert(n.substr(0, i));
            }
            if (t.open_only.count(n) == 0) {
                t.closable_bases.insert(stripped);
            }
        }
        return t;
    }();
    return instance;
}

int tone_of_key(char lo) {
    switch (lo) {
        case 's': return 1;
        case 'f': return 2;
        case 'r': return 3;
        case 'x': return 4;
        case 'j': return 5;
        default: return 0;
    }
}

char32_t circumflex_of(char32_t c) {
    switch (c) {
        case U'a': return U'â';
        case U'e': return U'ê';
        case U'o': return U'ô';
        default: return c;
    }
}

char32_t horn_of(char32_t c) {
    switch (c) {
        case U'a': return U'ă';
        case U'o': return U'ơ';
        case U'u': return U'ư';
        default: return c;
    }
}

char32_t unhorn_of(char32_t c) {
    switch (c) {
        case U'ă': return U'a';
        case U'ơ': return U'o';
        case U'ư': return U'u';
        default: return c;
    }
}

// ---------------------------------------------------------------------------
// Phân tích âm tiết
// ---------------------------------------------------------------------------

struct Parts {
    u32 initial, nucleus, final;
};

// Tách âm tiết (chữ thường, chưa có dấu thanh) thành (đầu, vần, cuối).
std::optional<Parts> split(const u32& s) {
    const Tables& t = tables();
    u32 initial;
    for (const u32& ini : t.initials) {
        if (s.compare(0, ini.size(), ini) == 0 && s.size() >= ini.size()) {
            const u32 rest = s.substr(ini.size());
            if (ini == U"gi" && !(!rest.empty() && t.is_vowel(rest[0]))) {
                continue;  // "gì", "gin": i là nguyên âm
            }
            if (ini == U"qu" && !rest.empty() && !t.is_vowel(rest[0])) {
                continue;
            }
            initial = ini;
            break;
        }
    }
    const u32 rest = s.substr(initial.size());
    std::size_t i = 0;
    while (i < rest.size() && t.is_vowel(rest[i])) {
        ++i;
    }
    Parts p{initial, rest.substr(0, i), rest.substr(i)};
    if (std::any_of(p.final.begin(), p.final.end(), [&](char32_t c) { return t.is_vowel(c); })) {
        return std::nullopt;
    }
    if (p.nucleus.empty() && !p.final.empty()) {
        return std::nullopt;
    }
    if (initial.empty() && !s.empty() && !t.is_vowel(s[0])) {
        return std::nullopt;  // phụ âm đầu không hợp lệ (f, j, w, z, cl…)
    }
    return p;
}

// Vần chắc chắn không thể có phụ âm cuối, kể cả khi thêm dấu mũ/móc sau này.
bool open_only_now(const u32& nucleus) {
    const Tables& t = tables();
    if (t.open_only.count(nucleus) != 0 &&
        std::any_of(nucleus.begin(), nucleus.end(),
                    [&](char32_t c) { return t.horn_diacritics.count(c) != 0; })) {
        return true;
    }
    return t.closable_bases.count(t.strip(nucleus)) == 0;
}

// Chuỗi (chưa dấu thanh) có thể là phần đầu của một âm tiết hợp lệ không.
bool could_be_syllable(const u32& s) {
    if (s == U"q") {
        return true;  // phần đầu của "qu"
    }
    const auto p = split(s);
    if (!p) {
        return false;
    }
    const Tables& t = tables();
    return t.nucleus_base_prefixes.count(t.strip(p->nucleus)) != 0 &&
           t.final_prefixes.count(p->final) != 0 &&
           !(!p->final.empty() && open_only_now(p->nucleus));
}

// Vần (giữ nguyên dấu mũ/móc) có thể là phần đầu của một vần hợp lệ không.
bool nucleus_could_be(const u32& s) {
    const auto p = split(s);
    return p && tables().nucleus_prefixes.count(p->nucleus) != 0;
}

bool is_valid_syllable(const u32& s) {
    const auto p = split(s);
    if (!p) {
        return false;
    }
    const Tables& t = tables();
    return t.nuclei.count(p->nucleus) != 0 &&
           (p->final.empty() || t.finals.count(p->final) != 0) &&
           !(!p->final.empty() && t.open_only.count(p->nucleus) != 0);
}

std::size_t tone_index(const u32& nucleus, bool has_final, bool new_style) {
    const Tables& t = tables();
    if (const auto pos = nucleus.find(U"ươ"); pos != u32::npos) {
        return pos + 1;
    }
    for (std::size_t i = nucleus.size(); i-- > 0;) {
        if (t.horn_diacritics.count(nucleus[i]) != 0) {
            return i;
        }
    }
    if (nucleus.size() == 1) {
        return 0;
    }
    if (has_final) {
        return nucleus.size() - 1;
    }
    if (nucleus.size() == 3) {
        return 1;
    }
    if (new_style && (nucleus == U"oa" || nucleus == U"oe" || nucleus == U"uy")) {
        return 1;
    }
    return 0;
}

// ---------------------------------------------------------------------------
// Áp dụng chuỗi phím
// ---------------------------------------------------------------------------

constexpr char kSrcNone = '\0';
constexpr char kSrcW = 'w';        // biến đổi do phím w
constexpr char kSrcWAlone = 'W';   // ư tạo bởi w đứng riêng (ww -> w)

struct Ch {
    char32_t c;     // ký tự thường (đã biến đổi)
    bool upper;     // có viết hoa không
    char src;       // phím đã tạo ra biến đổi, để hỗ trợ gõ lặp để hủy
};

struct Applied {
    std::vector<Ch> chars;
    int tone = 0;
    int undo_idx = -1;  // vị trí phím gõ lặp để hủy gần nhất
};

bool is_qu_u(const std::vector<Ch>& chars, std::size_t i) {
    return i == 1 && chars.size() > 1 && chars[0].c == U'q' && chars[1].c == U'u';
}

u32 plain_of(const std::vector<Ch>& chars) {
    u32 s;
    s.reserve(chars.size());
    for (const Ch& ch : chars) {
        s.push_back(ch.c);
    }
    return s;
}

std::vector<std::size_t> vowel_idx(const std::vector<Ch>& chars) {
    std::vector<std::size_t> v;
    for (std::size_t i = 0; i < chars.size(); ++i) {
        if (tables().is_vowel(chars[i].c)) {
            v.push_back(i);
        }
    }
    return v;
}

Applied apply_keys(std::string_view keys) {
    Applied r;
    auto& chars = r.chars;
    std::set<char> blocked;
    bool frozen = false;  // đã chắc chắn không phải tiếng Việt: các phím sau giữ nguyên
    std::size_t prev_blocked = 0;

    for (std::size_t idx = 0; idx < keys.size(); ++idx) {
        if (blocked.size() > prev_blocked) {
            r.undo_idx = static_cast<int>(idx) - 1;
        }
        prev_blocked = blocked.size();
        const char k = keys[idx];
        const char lo = static_cast<char>(std::tolower(static_cast<unsigned char>(k)));
        const bool up = k != lo;
        const char32_t lo32 = static_cast<unsigned char>(lo);

        if (!frozen && !chars.empty() && !could_be_syllable(plain_of(chars))) {
            frozen = true;
        }
        if (frozen) {
            chars.push_back({lo32, up, kSrcNone});
            continue;
        }

        if (tone_of_key(lo) != 0 || lo == 'z') {
            if (lo == 'z') {
                if (r.tone != 0 && !vowel_idx(chars).empty()) {
                    r.tone = 0;
                    continue;
                }
                chars.push_back({lo32, up, kSrcNone});
                continue;
            }
            const int t = tone_of_key(lo);
            if (!vowel_idx(chars).empty() && blocked.count(lo) == 0) {
                if (r.tone == t) {  // gõ lặp: hủy dấu, giữ phím
                    r.tone = 0;
                    blocked.insert(lo);
                    chars.push_back({lo32, up, kSrcNone});
                } else {
                    r.tone = t;
                }
                continue;
            }
            chars.push_back({lo32, up, kSrcNone});
            continue;
        }

        if (lo == 'd') {
            // "d" không bao giờ là phụ âm cuối, nên "d" gõ sau (ở bất kỳ đâu trong từ)
            // chỉ có thể là biến d đầu từ thành đ: ddi, did, dudocwj…
            if (!chars.empty() && chars[0].c == U'd' && blocked.count('d') == 0) {
                chars[0].c = U'đ';
                continue;
            }
            if (!chars.empty() && chars[0].c == U'đ') {  // gõ lặp: đ + d -> dd
                chars[0].c = U'd';
                blocked.insert('d');
            }
            chars.push_back({lo32, up, kSrcNone});
            continue;
        }

        if (lo == 'a' || lo == 'e' || lo == 'o') {
            const char32_t circ = circumflex_of(lo32);
            if (blocked.count(lo) == 0) {
                std::optional<std::size_t> hit;
                const auto vi = vowel_idx(chars);
                for (auto it = vi.rbegin(); it != vi.rend(); ++it) {
                    if (chars[*it].c == lo32 || chars[*it].c == circ) {
                        hit = *it;
                        break;
                    }
                }
                if (hit && chars[*hit].c == lo32) {
                    u32 trial = plain_of(chars);
                    trial[*hit] = circ;
                    const u32 appended = plain_of(chars) + lo32;
                    if (nucleus_could_be(trial) || !nucleus_could_be(appended)) {
                        chars[*hit].c = circ;
                        continue;
                    }
                }
                if (hit && chars[*hit].c == circ) {
                    chars[*hit].c = lo32;  // gõ lặp: hủy mũ
                    blocked.insert(lo);
                }
            }
            chars.push_back({lo32, up, kSrcNone});
            continue;
        }

        if (lo == 'w') {
            if (blocked.count('w') != 0) {
                chars.push_back({lo32, up, kSrcNone});
                continue;
            }
            const auto vi = vowel_idx(chars);
            // 1) Thử biến đổi: uo -> ươ, nếu còn ký tự chưa đổi.
            std::optional<std::pair<std::size_t, std::size_t>> pair;
            for (std::size_t n = 0; n + 1 < vi.size(); ++n) {
                const std::size_t a = vi[n];
                const std::size_t b = vi[n + 1];
                if (is_qu_u(chars, a)) {
                    continue;  // chữ u của "qu" thuộc phụ âm đầu (quở, quới)
                }
                if (b == a + 1 && (chars[a].c == U'u' || chars[a].c == U'ư') &&
                    (chars[b].c == U'o' || chars[b].c == U'ơ')) {
                    pair = {a, b};
                }
            }
            if (pair && !(chars[pair->first].c == U'ư' && chars[pair->second].c == U'ơ')) {
                if (chars[pair->first].c != U'ư') {
                    chars[pair->first] = {U'ư', chars[pair->first].upper, kSrcW};
                }
                if (chars[pair->second].c != U'ơ') {
                    chars[pair->second] = {U'ơ', chars[pair->second].upper, kSrcW};
                }
                continue;
            }
            // 2) a/o/u chưa biến đổi -> ă/ơ/ư. Ưu tiên lựa chọn cho ra vần hợp lệ
            //    (chuaw -> chưa, không phải chuă; quaw -> quă vì "qu" là phụ âm đầu).
            std::vector<std::size_t> options;
            for (auto it = vi.rbegin(); it != vi.rend(); ++it) {
                const char32_t c = chars[*it].c;
                const bool in_pair = pair && (*it == pair->first || *it == pair->second);
                if ((c == U'a' || c == U'o' || c == U'u') && !in_pair) {
                    options.push_back(*it);
                }
            }
            std::optional<std::size_t> target;
            for (std::size_t i : options) {
                u32 trial = plain_of(chars);
                trial[i] = horn_of(trial[i]);
                if (nucleus_could_be(trial)) {
                    target = i;
                    break;
                }
            }
            if (!target && !options.empty()) {
                target = options.front();
            }
            if (target) {
                chars[*target].c = horn_of(chars[*target].c);
                chars[*target].src = kSrcW;
                continue;
            }
            // 3) Không còn gì để biến đổi: gõ lặp để hủy.
            std::vector<std::size_t> made;
            for (std::size_t i = 0; i < chars.size(); ++i) {
                if (chars[i].src == kSrcW || chars[i].src == kSrcWAlone) {
                    made.push_back(i);
                }
            }
            if (!made.empty()) {
                blocked.insert('w');
                if (made.size() == 1 && chars[made[0]].src == kSrcWAlone &&
                    made[0] == chars.size() - 1) {
                    chars[made[0]].c = U'w';  // ww -> w
                    chars[made[0]].src = kSrcNone;
                    continue;
                }
                for (std::size_t i : made) {
                    chars[i].c = unhorn_of(chars[i].c);
                    chars[i].src = kSrcNone;
                }
                chars.push_back({lo32, up, kSrcNone});
                continue;
            }
            // 4) w đứng riêng (chưa có nguyên âm) -> ư.
            if (vi.empty()) {
                chars.push_back({U'ư', up, kSrcWAlone});
                continue;
            }
            chars.push_back({lo32, up, kSrcNone});
            continue;
        }

        if (k == '[' || k == ']' || k == '{' || k == '}') {
            const char32_t nw = (k == '[' || k == '{') ? U'ơ' : U'ư';
            if (!chars.empty() && chars.back().src == k) {  // gõ lặp: [[ -> [
                chars.back().c = static_cast<unsigned char>(k);
                chars.back().src = kSrcNone;
                continue;
            }
            chars.push_back({nw, k == '{' || k == '}', k});
            continue;
        }

        chars.push_back({lo32, up, kSrcNone});
    }

    if (blocked.size() > prev_blocked) {
        r.undo_idx = static_cast<int>(keys.size()) - 1;
    }
    return r;
}

char32_t to_upper(char32_t c) {
    if (c < 0x80) {
        return static_cast<char32_t>(std::toupper(static_cast<int>(c)));
    }
    const auto& up = tables().upper;
    if (auto it = up.find(c); it != up.end()) {
        return it->second;
    }
    return c;
}

std::string lower_ascii(std::string_view s) {
    std::string out(s);
    for (char& c : out) {
        c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    }
    return out;
}

std::string render(std::string_view keys, bool strict, const TelexOptions& options) {
    const Tables& t = tables();
    Applied a = apply_keys(keys);
    auto& chars = a.chars;

    // Chuẩn hóa cặp u/o có móc để thứ tự đặt w không quan trọng:
    // - còn chữ phía sau -> "ươ" (được, người, mượn…)
    // - đứng cuối từ     -> "uơ" (thuở, huơ), vì "ươ" không bao giờ đứng cuối.
    for (std::size_t i = 0; i + 1 < chars.size(); ++i) {
        if (is_qu_u(chars, i)) {
            continue;
        }
        const char32_t x = chars[i].c;
        const char32_t y = chars[i + 1].c;
        if ((x == U'ư' && y == U'o') || (x == U'u' && y == U'ơ') || (x == U'ư' && y == U'ơ')) {
            chars[i].c = (i + 2 < chars.size()) ? U'ư' : U'u';
            chars[i + 1].c = U'ơ';
        }
    }
    const u32 plain = plain_of(chars);
    if (plain.empty()) {
        return {};
    }

    auto cased = [&](const u32& out) {
        u32 s;
        s.reserve(out.size());
        for (std::size_t i = 0; i < out.size(); ++i) {
            s.push_back(chars[i].upper ? to_upper(out[i]) : out[i]);
        }
        return to_utf8(s);
    };

    const bool ascii = std::all_of(plain.begin(), plain.end(), [](char32_t c) { return c < 0x80; });
    if (a.tone == 0 && ascii) {
        // Gõ lặp để hủy (ass -> as, tassk -> task, ww -> w): giữ kết quả hủy, như UniKey.
        // Ngoại lệ: nếu hủy ở giữa từ và nguyên chuỗi phím là một từ tiếng Anh thật
        // (error, effect: chữ cái đôi thật) -> giữ nguyên chuỗi phím.
        if (strict && a.undo_idx >= 0 && a.undo_idx < static_cast<int>(keys.size()) - 1 &&
            !is_valid_syllable(plain) && options.english != nullptr &&
            options.english->contains(lower_ascii(keys))) {
            return std::string(keys);
        }
        return cased(plain);
    }

    const auto p = split(plain);
    if (!p) {
        return std::string(keys);
    }
    const auto& [initial, nucleus, final] = *p;
    const bool harsh_tone = a.tone == 2 || a.tone == 3 || a.tone == 4;

    bool ok = false;
    if (strict) {
        // Không bắt "vần cần phụ âm cuối" (â, tiê…) để tránh khôi phục khó chịu.
        ok = (t.nuclei.count(nucleus) != 0 || (nucleus.empty() && final.empty() && !initial.empty())) &&
             (final.empty() || t.finals.count(final) != 0) &&
             !(!final.empty() && t.open_only.count(nucleus) != 0) &&
             !(t.stop_finals.count(final) != 0 && harsh_tone) &&
             !(a.tone != 0 && nucleus.empty());
    } else {
        ok = t.nucleus_base_prefixes.count(t.strip(nucleus)) != 0 &&
             t.final_prefixes.count(final) != 0 &&
             !(!final.empty() && open_only_now(nucleus)) &&
             !(!final.empty() && (final[0] == U'c' || final[0] == U'p' || final[0] == U't') &&
               harsh_tone);
    }
    if (!ok) {
        return std::string(keys);
    }

    u32 out = plain;
    if (a.tone != 0 && !nucleus.empty()) {
        const std::size_t i = initial.size() + tone_index(nucleus, !final.empty(), options.new_style);
        out[i] = t.toned.at(out[i])[static_cast<std::size_t>(a.tone)];
    }
    return cased(out);
}

}  // namespace

// ---------------------------------------------------------------------------
// API công khai
// ---------------------------------------------------------------------------

WordSet WordSet::load(const std::string& path) {
    WordSet set;
    std::ifstream in(path);
    std::string line;
    while (std::getline(in, line)) {
        while (!line.empty() && std::isspace(static_cast<unsigned char>(line.back()))) {
            line.pop_back();
        }
        const auto first = line.find_first_not_of(" \t");
        if (first == std::string::npos) {
            continue;
        }
        line.erase(0, first);
        if (std::all_of(line.begin(), line.end(),
                        [](char c) { return static_cast<unsigned char>(c) < 0x80; })) {
            set.insert(lower_ascii(line));
        }
    }
    return set;
}

WordSet WordSet::load_default() {
    for (const char* path : {"/usr/share/dict/words", "/usr/share/dict/american-english"}) {
        if (std::ifstream(path).good()) {
            return load(path);
        }
    }
    return {};
}

void WordSet::insert(std::string word) { words_.insert(std::move(word)); }

bool WordSet::contains(std::string_view word) const { return words_.count(std::string(word)) != 0; }

std::string transform(std::string_view keys, const TelexOptions& options) {
    return render(keys, /*strict=*/false, options);
}

std::string finalize(std::string_view keys, const TelexOptions& options) {
    return render(keys, /*strict=*/true, options);
}

}  // namespace telexiva
