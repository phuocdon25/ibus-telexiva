"""Chạy: python3 -m unittest discover -s prototype -v"""

import unittest

from telex import finalize, transform


class TelexFinal(unittest.TestCase):
    CASES = [
        # biến đổi ký tự
        ("aan", "ân"), ("awn", "ăn"), ("eem", "êm"), ("oom", "ôm"), ("own", "ơn"),
        ("uw", "ư"), ("ddi", "đi"), ("w", "ư"), ("tw", "tư"), ("t[", "tơ"), ("t]", "tư"),
        ("nguoiwf", "người"), ("nguwowif", "người"), ("dduowcj", "được"), ("duowcj", "dược"),
        ("hoawcj", "hoặc"), ("ow", "ơ"), ("oww", "ow"),
        # dấu thanh
        ("as", "á"), ("af", "à"), ("ar", "ả"), ("ax", "ã"), ("aj", "ạ"), ("asz", "a"),
        ("aasz", "â"), ("asf", "à"),
        # gõ dấu tự do
        ("tieengs", "tiếng"), ("tieesng", "tiếng"), ("vieejt", "việt"),
        ("tiesng", "tiesng"),  # thiếu e thứ hai: "tiéng" sai chính tả -> khôi phục
        ("vieetj", "việt"),
        # gõ lặp để hủy
        ("ass", "as"), ("aaa", "aa"), ("ww", "w"), ("ddd", "dd"), ("[[", "["),
        # vị trí dấu (kiểu cũ)
        ("hoaf", "hòa"), ("thuys", "thúy"), ("khoer", "khỏe"), ("quys", "quý"),
        ("giar", "giả"), ("khuyeens", "khuyến"), ("hoangf", "hoàng"), ("ngoaif", "ngoài"),
        ("gif", "gì"),
        # chữ hoa
        ("Vieejt", "Việt"), ("VIEEJT", "VIỆT"), ("DDAAY", "ĐÂY"), ("AS", "Á"),
        # tự khôi phục từ tiếng Anh
        ("text", "text"), ("class", "class"), ("for", "for"), ("function", "function"),
        ("const", "const"), ("width", "width"), ("vietj", "vietj"),
        # không biến đổi
        ("lo", "lo"), ("Q", "Q"), ("localhost", "localhost"),
    ]

    def test_cases(self):
        for keys, want in self.CASES:
            with self.subTest(keys=keys):
                self.assertEqual(finalize(keys), want)

    def test_new_style(self):
        self.assertEqual(finalize("hoaf", new_style=True), "hoà")
        self.assertEqual(finalize("thuys", new_style=True), "thuý")


class TelexWhileTyping(unittest.TestCase):
    def test_intermediate_states_show_vietnamese(self):
        # Trong lúc gõ, vần chưa hoàn chỉnh vẫn phải hiện tiếng Việt, không nhảy về phím gốc.
        self.assertEqual(transform("tiee"), "tiê")
        self.assertEqual(transform("nguoiw"), "ngươi")
        self.assertEqual(transform("vietj"), "viẹt")

    def test_plain_letters_unchanged(self):
        # Điều kiện của pass-through: chữ không biến đổi phải giữ nguyên từng phím.
        for keys in ["l", "lo", "Q", "loc", "localh"]:
            self.assertEqual(transform(keys), keys)


if __name__ == "__main__":
    unittest.main()
