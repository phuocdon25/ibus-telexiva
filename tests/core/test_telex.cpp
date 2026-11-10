// SPDX-License-Identifier: GPL-3.0-or-later
#include <catch2/catch_test_macros.hpp>

#include <fstream>
#include <sstream>
#include <string>
#include <vector>

#include "telexiva/telex.hpp"

namespace {

struct Case {
    std::string function, style, keys, expected, group;
};

std::vector<Case> load_cases() {
    std::ifstream in(TELEXIVA_CASES_TSV);
    REQUIRE(in.good());
    std::vector<Case> cases;
    std::string line;
    while (std::getline(in, line)) {
        if (line.empty() || line[0] == '#') {
            continue;
        }
        std::istringstream row(line);
        Case c;
        std::getline(row, c.function, '\t');
        std::getline(row, c.style, '\t');
        std::getline(row, c.keys, '\t');
        std::getline(row, c.expected, '\t');
        std::getline(row, c.group, '\t');
        cases.push_back(c);
    }
    return cases;
}

const telexiva::WordSet& english() {
    static const telexiva::WordSet set = telexiva::WordSet::load_default();
    return set;
}

}  // namespace

TEST_CASE("Bảng test dùng chung với prototype Python (tests/data/telex_cases.tsv)", "[telex]") {
    const auto cases = load_cases();
    REQUIRE(cases.size() > 100);
    for (const Case& c : cases) {
        const telexiva::TelexOptions opt{c.style == "new", &english()};
        const std::string got =
            c.function == "transform" ? telexiva::transform(c.keys, opt) : telexiva::finalize(c.keys, opt);
        INFO(c.group << ": " << c.function << "(" << c.keys << ")");
        CHECK(got == c.expected);
    }
}

TEST_CASE("Không có từ điển: hành vi như UniKey", "[telex]") {
    const telexiva::TelexOptions no_dict{};
    CHECK(telexiva::finalize("tassk", no_dict) == "task");
    CHECK(telexiva::finalize("error", no_dict) == "eror");
}

TEST_CASE("Có từ điển: giữ nguyên từ tiếng Anh có chữ cái đôi", "[telex]") {
    telexiva::WordSet words;
    words.insert("error");
    const telexiva::TelexOptions opt{false, &words};
    CHECK(telexiva::finalize("error", opt) == "error");
    CHECK(telexiva::finalize("tassk", opt) == "task");
}

TEST_CASE("Chuỗi rỗng và ký tự lạ không làm hỏng engine", "[telex]") {
    CHECK(telexiva::transform("").empty());
    CHECK(telexiva::finalize("").empty());
    CHECK(telexiva::finalize("[[") == "[");
    CHECK(telexiva::finalize("}") == "Ư");
}
