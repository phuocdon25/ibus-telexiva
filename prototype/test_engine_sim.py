"""Mô phỏng engine với một ô nhập giả (không cần IBus daemon).

Chạy: python3 -m unittest discover -s prototype -v
"""

import sys
import unittest

import gi

gi.require_version("IBus", "1.0")
from gi.repository import IBus  # noqa: E402

sys.argv = sys.argv[:1]
import telexiva_proto as T  # noqa: E402

T.LOG.disabled = True   # không ghi vào log thật của người dùng


class _Text:
    def __init__(self, t):
        self.t = t

    def get_text(self):
        return self.t


class FakeApp:
    """Ô nhập giả. surrounding=True ~ Chrome/GTK (S2); False ~ terminal (S3)."""

    def __init__(self, surrounding=True):
        self.buf = ""
        self.passthrough = 0
        self.iid = 0
        self.client = "fake"
        self.cfg = {"strategy": "auto", "guard": "strict", "tone": "old"}
        self.caps = IBus.Capabilite.SURROUNDING_TEXT if surrounding else 0
        self.purpose = IBus.InputPurpose.FREE_FORM
        self.raw = ""
        self.shown = ""

    # API IBus mà engine gọi
    def get_surrounding_text(self):
        return _Text(self.buf), len(self.buf), len(self.buf)

    def delete_surrounding_text(self, offset, n):
        self.buf = self.buf[: len(self.buf) + offset]

    def forward_key_event(self, keyval, keycode, state):
        if keyval == IBus.KEY_BackSpace and not state & IBus.ModifierType.RELEASE_MASK:
            self.buf = self.buf[:-1]

    def commit_text(self, text):
        self.buf += text.get_text()

    def type(self, s):
        for c in s:
            kv = IBus.unicode_to_keyval(c)
            st = IBus.ModifierType.SHIFT_MASK if c.isupper() else 0
            if not self.do_process_key_event(kv, 0, st):
                self.passthrough += 1
                self.buf += c
        return self


# Mượn logic của engine thật.
for _name, _fn in T.TelexivaProtoEngine.__dict__.items():
    if callable(_fn) and (_name.startswith("do_") or _name.startswith("_")) and not _name.startswith("__"):
        setattr(FakeApp, _name, _fn)


class EngineSim(unittest.TestCase):
    def test_vietnamese_sentence_s2(self):
        self.assertEqual(FakeApp().type("Vieejt Nam ddepj quas ").buf, "Việt Nam đẹp quá ")

    def test_vietnamese_sentence_s3_terminal(self):
        self.assertEqual(FakeApp(surrounding=False).type("suwar looix ").buf, "sửa lỗi ")

    def test_english_code_restored(self):
        s = "const text = function return "
        self.assertEqual(FakeApp().type(s).buf, s)

    def test_digits_pass_through(self):  # BUG-001
        app = FakeApp().type("1200000")
        self.assertEqual(app.buf, "1200000")
        self.assertEqual(app.passthrough, 7)

    def test_plain_letters_pass_through(self):  # BUG-003
        app = FakeApp().type("lo")
        self.assertEqual(app.passthrough, 2)

    def test_suggestion_after_q(self):  # BUG-002
        app = FakeApp().type("Q")
        app.buf = "Quên chấm công"      # Chrome thay giá trị khi chọn gợi ý
        app.do_focus_out()
        self.assertEqual(app.buf, "Quên chấm công")

    def test_guard_when_page_changes_text(self):
        app = FakeApp().type("Quee")
        app.buf = "Quên chấm công"      # trang đổi nội dung giữa chừng
        app.type("s")                    # phím dấu: không được xóa nhầm
        self.assertTrue(app.buf.startswith("Quên chấm công"))

    def test_password_untouched(self):
        app = FakeApp()
        app.purpose = IBus.InputPurpose.PASSWORD
        self.assertEqual(app.type("aas").buf, "aas")


if __name__ == "__main__":
    unittest.main()
