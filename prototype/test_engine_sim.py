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


# Mô hình Chrome qua Mutter (GNOME Wayland) dùng trong các test "stale"/"lagging":
# - engine thấy surrounding text là BẢN SAO của Mutter; bản sao có thể cũ;
# - delete_surrounding_text(ký tự) được Mutter đổi sang BYTE bằng bản sao đó;
# - Chrome xóa theo byte trên nội dung thật; cắt giữa một ký tự UTF-8 -> bỏ cả lệnh xóa.


class FakeApp:
    """Ô nhập giả. surrounding=True ~ Chrome/GTK (S2); False ~ terminal (S3)."""

    def __init__(self, surrounding=True, ignores_delete=False):
        self.ignores_delete = ignores_delete   # mô phỏng ô chat ChatGPT/Gemini
        self.preedit = ""
        self.hints = 0
        self.preedit_mode = False
        self.pending_verify = None
        self.inflight = None
        self.waiting = False
        self.key_queue = []
        self.auto_confirm = True   # False: mô phỏng bản sao surrounding text còn cũ (chưa xác nhận)
        self.prev_char = ""
        self.last_edit_at = 0.0
        self.awaiting_confirm = None
        self.buf = ""
        self.passthrough = 0
        self.iid = 0
        self.client = "fake"
        self.cfg = {"strategy": "auto", "guard": "strict", "tone": "old"}
        self.caps = IBus.Capabilite.SURROUNDING_TEXT if surrounding else 0
        self.purpose = IBus.InputPurpose.FREE_FORM
        self.raw = ""
        self.shown = ""
        self.recent = []
        self.frozen = False
        self.history = []   # buf trước mỗi phím, để mô phỏng surrounding text báo trễ

    # API IBus mà engine gọi
    def get_surrounding_text(self):
        return _Text(self.buf), len(self.buf), len(self.buf)

    def delete_surrounding_text(self, offset, n):
        if not self.ignores_delete:
            self.buf = self.buf[: len(self.buf) + offset]

    def update_preedit_text_with_mode(self, text, cursor, visible, mode):
        self.preedit = text.get_text()

    def hide_preedit_text(self):
        self.preedit = ""

    def screen(self):
        """Những gì người dùng nhìn thấy: chữ thật + phần nháp."""
        return self.buf + self.preedit

    def forward_key_event(self, keyval, keycode, state):
        if keyval == IBus.KEY_BackSpace and not state & IBus.ModifierType.RELEASE_MASK:
            self.buf = self.buf[:-1]

    def commit_text(self, text):
        self.buf += text.get_text()

    def type(self, s):
        for c in s:
            if self.auto_confirm:
                self.awaiting_confirm = None   # giữa hai phím, ô nhập giả đã xác nhận lần sửa trước
            self.history.append(self.buf)
            kv = IBus.unicode_to_keyval(c)
            st = IBus.ModifierType.SHIFT_MASK if c.isupper() else 0
            if not self.do_process_key_event(kv, 0, st):
                self.passthrough += 1
                self.buf += c
        return self


# Mượn logic của engine thật.
# (Ô nhập giả không gửi set_surrounding_text nên không đợi xác nhận; phần đợi được
#  kiểm tra riêng trong test_wait_confirm_queues_keys.)
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
        self.assertEqual(app.buf, "Quên chấm côngs")

    def test_lagging_surrounding_text(self):
        # Gõ nhanh: bản sao của Mutter trễ 1 phím; Mutter đổi ký tự -> byte bằng bản sao đó.
        app = FakeApp()
        app.auto_confirm = False

        def lagging():
            prev = app.history[-2] if len(app.history) >= 2 else ""
            return _Text(prev), len(prev), len(prev)

        def delete(offset, n):
            view = app.history[-2] if len(app.history) >= 2 else ""
            nbytes = len(view[len(view) + offset:].encode("utf-8"))
            raw = app.buf.encode("utf-8")
            try:
                app.buf = raw[: len(raw) - nbytes].decode("utf-8")
            except UnicodeDecodeError:
                pass

        app.get_surrounding_text = lagging
        app.delete_surrounding_text = delete
        self.assertEqual(app.type("macwj ").buf, "mặc ")

    def test_inline_completion_selection(self):
        # Omnibox: phần gợi ý được bôi đen sau con trỏ không được chặn biến đổi.
        app = FakeApp()
        app.get_surrounding_text = lambda: (_Text(app.buf + "calhost"), len(app.buf), len(app.buf) + 7)
        self.assertEqual(app.type("looi").buf, "lôi")

    def test_field_ignoring_delete_switches_to_preedit(self):
        # Ô kiểu ChatGPT bỏ qua delete_surrounding_text: từ đầu tiên sai (đã biết),
        # engine phát hiện và các từ sau gõ bằng nháp -> đúng.
        app = FakeApp(ignores_delete=True).type("taoj vaanx conf ")
        self.assertEqual(app.buf, "taoạo vẫn còn ")
        self.assertTrue(app.preedit_mode)

    def test_preedit_mode_shows_draft_then_commits(self):
        app = FakeApp(ignores_delete=True)
        app.preedit_mode = True
        app.type("dduowcj")
        self.assertEqual(app.buf, "")
        self.assertEqual(app.preedit, "được")
        app.type(" ")
        self.assertEqual(app.buf, "được ")
        self.assertEqual(app.preedit, "")

    def test_preedit_backspace_and_restore(self):
        app = FakeApp()
        app.preedit_mode = True
        app.type("taoj")
        app.do_process_key_event(IBus.KEY_BackSpace, 14, 0)
        self.assertEqual(app.preedit, "tạ")
        app.type(" text ")
        self.assertEqual(app.buf, "tạ text ")

    def test_focus_change_resets_preedit_mode(self):
        app = FakeApp(ignores_delete=True).type("taoj vaanx ")
        self.assertTrue(app.preedit_mode)
        app.do_focus_in()
        self.assertFalse(app.preedit_mode)

    def test_normal_field_stays_without_preedit(self):
        app = FakeApp().type("taoj vaanx conf ")
        self.assertEqual(app.buf, "tạo vẫn còn ")
        self.assertFalse(app.preedit_mode)

    def test_surrounding_reports_deleted_not_yet_inserted(self):
        # Ngay sau lần sửa, ô báo trạng thái "đã xóa, chưa chèn" (xuoongs -> ô báo "xu")
        # trong suốt phím kế tiếp.
        app = FakeApp()
        app.auto_confirm = False
        real_delete = app.delete_surrounding_text
        app.mid = None
        app.stale = None

        def delete(offset, n):
            real_delete(offset, n)
            app.mid = app.buf          # ảnh chụp ngay sau khi xóa, trước khi chèn

        def surrounding():
            t = app.stale if app.stale is not None else app.buf
            return _Text(t), len(t), len(t)

        app.delete_surrounding_text = delete
        app.get_surrounding_text = surrounding
        for c in "xuongos xuoongs ":
            app.stale, app.mid = app.mid, None   # phím này thấy ảnh chụp của phím trước
            app.type(c)
        self.assertEqual(app.buf, "xuống xuống ")

    def test_field_deleting_too_much_switches_to_preedit(self):
        # Ô xóa thừa 1 ký tự (giongso -> "gống"): sau khi xác nhận, nội dung khác mong đợi
        # -> engine chuyển ô đó sang nháp, các từ sau đúng.
        app = FakeApp()
        real = app.delete_surrounding_text

        def delete(offset, n):
            real(offset - 1, n + 1)   # xóa thừa một ký tự

        app.delete_surrounding_text = delete
        app.type("giongso ")
        self.assertTrue(app.preedit_mode)
        start = len(app.buf)
        app.type("dduowcj ")
        self.assertEqual(app.buf[start:], "được ")

    def test_wait_confirm_queues_keys(self):
        # Mô phỏng: lần sửa trước chưa được xác nhận, phím "o" đến trong lúc đợi.
        app = FakeApp()
        app.waiting = False
        app.key_queue = []
        app.type("truongw")                     # -> "trương"
        self.assertEqual(app.buf, "trương")
        # Trong lúc đợi, phím mới bị xếp hàng và được xử lý lại sau, đúng thứ tự.
        app.waiting = True
        self.assertTrue(app.do_process_key_event(IBus.unicode_to_keyval("f"), 0, 0))
        self.assertEqual(app.key_queue, [(IBus.unicode_to_keyval("f"), 0, 0)])
        app.waiting = False
        app._drain_queue()
        self.assertEqual(app.buf, "trường")

    def test_stale_mutter_copy_byte_conversion(self):
        # gocs -> "góc", rồi "o" -> "gốc" khi bản sao của Mutter vẫn còn là "goc".
        app = FakeApp()
        app.auto_confirm = False
        app.view = ""            # bản sao của Mutter
        app.stale_next = False

        def surrounding():
            return _Text(app.view), len(app.view), len(app.view)

        def delete(offset, n):
            # Mutter: đổi n ký tự cuối của BẢN SAO sang số byte.
            nbytes = len(app.view[len(app.view) + offset:].encode("utf-8"))
            raw = app.buf.encode("utf-8")
            cut = raw[: len(raw) - nbytes]
            try:
                app.buf = cut.decode("utf-8")       # Chrome: điểm cắt hợp lệ -> xóa
            except UnicodeDecodeError:
                pass                                  # cắt giữa ký tự -> bỏ qua lệnh xóa
            app.stale_next = True

        app.get_surrounding_text = surrounding
        app.delete_surrounding_text = delete
        for c in "gocso ":
            if not app.stale_next:
                app.view = app.buf      # Mutter cập nhật bản sao...
            app.stale_next = False      # ...trừ ngay sau một lần sửa (giữ bản cũ 1 phím)
            app.type(c)
        self.assertEqual(app.buf, "gốc ")

    def test_password_untouched(self):
        app = FakeApp()
        app.purpose = IBus.InputPurpose.PASSWORD
        self.assertEqual(app.type("aas").buf, "aas")


if __name__ == "__main__":
    unittest.main()
