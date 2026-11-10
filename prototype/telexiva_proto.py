#!/usr/bin/env python3
"""Telexiva prototype — IBus engine viết bằng Python (Phase 0).

Mục đích: kiểm chứng FR-009 "pass-through first" trên GNOME Wayland + Chrome,
trước khi viết engine C++ thật.

Nguyên tắc:
1. Phím không làm đổi chữ -> trả False, để phím đi thẳng tới ứng dụng như English.
2. Phím gây biến đổi -> xóa phần chữ cũ và commit phần mới, không dùng preedit.
   - S2: delete_surrounding_text (khi client hỗ trợ surrounding text)
   - S3: gửi BackSpace giả (terminal và client không hỗ trợ surrounding text)
3. Guard: trước khi xóa, đối chiếu chữ trước con trỏ với chữ engine đã gõ.
   Không khớp -> bỏ từ hiện tại, không xóa gì.

Log (không chứa nội dung gõ): ~/.cache/telexiva-proto/engine.log
Cấu hình (tùy chọn): ~/.config/telexiva-proto.conf, dạng key=value:
    strategy = auto | s2 | s3      (mặc định auto)
    guard    = strict | log | off  (mặc định strict)
    tone     = old | new           (mặc định old)
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

import gi

gi.require_version("IBus", "1.0")
from gi.repository import GLib, GObject, IBus  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from telex import finalize, transform  # noqa: E402

ENGINE_NAME = "telexiva-proto"
BUS_NAME = "org.freedesktop.IBus.TelexivaProto"
KEYCODE_BACKSPACE = 14  # evdev

LETTER_EXTRA = set("[]{}")
# Phím kết thúc từ và được chốt (khôi phục chính tả nếu cần) trước khi đi tiếp.
WORD_END_KEYVALS = {IBus.KEY_space, IBus.KEY_Return, IBus.KEY_KP_Enter, IBus.KEY_Tab}
# Phím chỉ làm mất ngữ cảnh: reset, không chốt.
RESET_KEYVALS = {
    IBus.KEY_Left, IBus.KEY_Right, IBus.KEY_Up, IBus.KEY_Down,
    IBus.KEY_Home, IBus.KEY_End, IBus.KEY_Page_Up, IBus.KEY_Page_Down,
    IBus.KEY_Escape, IBus.KEY_Delete, IBus.KEY_BackSpace,
}
MODIFIER_KEYVALS = {
    IBus.KEY_Shift_L, IBus.KEY_Shift_R, IBus.KEY_Control_L, IBus.KEY_Control_R,
    IBus.KEY_Alt_L, IBus.KEY_Alt_R, IBus.KEY_Super_L, IBus.KEY_Super_R,
    IBus.KEY_Caps_Lock, IBus.KEY_ISO_Level3_Shift,
}
SHORTCUT_MASK = (
    IBus.ModifierType.CONTROL_MASK | IBus.ModifierType.MOD1_MASK
    | IBus.ModifierType.SUPER_MASK | IBus.ModifierType.MOD4_MASK
)


def _setup_logging() -> logging.Logger:
    log = logging.getLogger("telexiva-proto")
    log.setLevel(logging.INFO)
    cache = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
    path = os.path.join(cache, "telexiva-proto")
    os.makedirs(path, exist_ok=True)
    h = RotatingFileHandler(os.path.join(path, "engine.log"), maxBytes=1_000_000, backupCount=2)
    h.setFormatter(logging.Formatter("%(asctime)s.%(msecs)03d %(message)s", "%H:%M:%S"))
    log.addHandler(h)
    return log


LOG = _setup_logging()


def _load_config() -> dict[str, str]:
    cfg = {"strategy": "auto", "guard": "strict", "tone": "old"}
    path = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
                        "telexiva-proto.conf")
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.split("#", 1)[0].strip()
                if "=" in line:
                    k, v = (x.strip() for x in line.split("=", 1))
                    cfg[k] = v
    except FileNotFoundError:
        pass
    return cfg


class TelexivaProtoEngine(IBus.Engine):
    __gtype_name__ = "TelexivaProtoEngine"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cfg = _load_config()
        self.caps = 0
        self.purpose = IBus.InputPurpose.FREE_FORM
        self.raw = ""     # các phím của từ hiện tại
        self.shown = ""   # chữ engine tin là đang nằm trong ứng dụng cho từ hiện tại
        LOG.info("engine created cfg=%s", self.cfg)

    # ---- trạng thái ----

    def _reset(self, why: str):
        if self.raw:
            LOG.info("reset why=%s word_len=%d", why, len(self.shown))
        self.raw = ""
        self.shown = ""

    def _new_style(self) -> bool:
        return self.cfg.get("tone") == "new"

    def _has_surrounding(self) -> bool:
        return bool(self.caps & IBus.Capabilite.SURROUNDING_TEXT)

    def _strategy(self) -> str:
        s = self.cfg.get("strategy", "auto")
        if s in ("s2", "s3"):
            return s
        return "s2" if self._has_surrounding() else "s3"

    # ---- guard ----

    def _guard_ok(self) -> bool:
        """Chữ ngay trước con trỏ có đúng là self.shown không."""
        mode = self.cfg.get("guard", "strict")
        if mode == "off" or not self._has_surrounding():
            return True
        text, cursor, anchor = self.get_surrounding_text()
        before = text.get_text()[:cursor] if text else ""
        ok = cursor == anchor and before.endswith(self.shown)
        if not ok:
            # Chỉ log độ dài, không log nội dung.
            LOG.info("guard mismatch mode=%s before_len=%d cursor=%d anchor=%d shown_len=%d",
                     mode, len(before), cursor, anchor, len(self.shown))
        return ok or mode == "log"

    # ---- thay chữ ----

    def _replace(self, new: str) -> bool:
        """Đổi self.shown thành new trong ứng dụng. False nếu guard chặn."""
        old = self.shown
        p = 0
        while p < min(len(old), len(new)) and old[p] == new[p]:
            p += 1
        n_del, ins = len(old) - p, new[p:]
        if n_del and not self._guard_ok():
            return False
        strategy = self._strategy()
        if n_del:
            if strategy == "s2":
                self.delete_surrounding_text(-n_del, n_del)
            else:
                for _ in range(n_del):
                    self.forward_key_event(IBus.KEY_BackSpace, KEYCODE_BACKSPACE, 0)
                    self.forward_key_event(IBus.KEY_BackSpace, KEYCODE_BACKSPACE,
                                           IBus.ModifierType.RELEASE_MASK)
        if ins:
            self.commit_text(IBus.Text.new_from_string(ins))
        self.shown = new
        LOG.info("replace strategy=%s del=%d ins=%d", strategy, n_del, len(ins))
        return True

    def _finish_word(self, why: str):
        """Kết thúc từ: khôi phục phím gốc nếu sai chính tả."""
        if self.raw:
            final = finalize(self.raw, self._new_style())
            if final != self.shown:
                LOG.info("finalize restore")
                self._replace(final)
        self._reset(why)

    # ---- IBus callbacks ----

    def do_process_key_event(self, keyval, keycode, state):
        if state & IBus.ModifierType.RELEASE_MASK:
            return False
        if self.purpose in (IBus.InputPurpose.PASSWORD, IBus.InputPurpose.PIN):
            return False
        if keyval in MODIFIER_KEYVALS:
            return False
        if state & SHORTCUT_MASK:
            self._reset("shortcut")
            return False

        ch = IBus.keyval_to_unicode(keyval) or ""   # PyGObject trả về str
        is_letter = len(ch) == 1 and ch.isascii() and (ch.isalpha() or ch in LETTER_EXTRA)

        if not is_letter:
            if keyval in WORD_END_KEYVALS or (len(ch) == 1 and ch.isprintable()):
                self._finish_word("word_end")
            else:
                self._reset("nav" if keyval in RESET_KEYVALS else "other")
            return False   # phím đi thẳng tới ứng dụng

        raw = self.raw + ch
        new = transform(raw, self._new_style())

        if new == self.shown + ch:
            # Không biến đổi: để ứng dụng tự chèn phím, giống English.
            self.raw, self.shown = raw, new
            return False

        if self._replace(new):
            self.raw = raw
            return True

        # Guard chặn: ứng dụng đã đổi nội dung. Bắt đầu từ mới với phím này.
        self._reset("guard")
        self.raw = ch
        self.shown = transform(ch, self._new_style())
        if self.shown == ch:
            return False
        self.commit_text(IBus.Text.new_from_string(self.shown))
        return True

    def do_focus_in(self):
        self._reset("focus_in")
        # Yêu cầu client gửi surrounding text (IBus chỉ gửi khi engine đã hỏi).
        self.get_surrounding_text()
        LOG.info("focus_in caps=0x%x surrounding=%s strategy=%s purpose=%s",
                 self.caps, self._has_surrounding(), self._strategy(), int(self.purpose))

    def do_focus_out(self):
        self._reset("focus_out")

    def do_reset(self):
        self._reset("reset")

    def do_enable(self):
        self.get_surrounding_text()
        LOG.info("enable")

    def do_disable(self):
        self._reset("disable")

    def do_set_capabilities(self, caps):
        self.caps = caps
        LOG.info("set_capabilities caps=0x%x surrounding=%s", caps, self._has_surrounding())

    def do_set_content_type(self, purpose, hints):
        self.purpose = purpose
        LOG.info("content_type purpose=%d hints=0x%x", int(purpose), int(hints))

    def do_set_cursor_location(self, x, y, w, h):
        pass


def main():
    IBus.init()
    bus = IBus.Bus()
    if not bus.is_connected():
        print("Không kết nối được IBus daemon", file=sys.stderr)
        sys.exit(1)
    factory = IBus.Factory.new(bus.get_connection())
    factory.add_engine(ENGINE_NAME, GObject.type_from_name("TelexivaProtoEngine"))

    if "--ibus" in sys.argv:
        bus.request_name(BUS_NAME, 0)
    else:
        # Chạy tay để debug: tự đăng ký component với daemon.
        component = IBus.Component(name=BUS_NAME, description="Telexiva prototype",
                                   version="0.0.1", license="GPL-3.0-or-later",
                                   author="phuocdon25", homepage="", textdomain="telexiva")
        component.add_engine(IBus.EngineDesc(name=ENGINE_NAME, longname="Telexiva (prototype)",
                                             description="Telexiva prototype", language="vi",
                                             license="GPL-3.0-or-later", author="phuocdon25",
                                             layout="us", symbol="TX"))
        bus.register_component(component)

    LOG.info("started argv=%s", sys.argv[1:])
    GLib.MainLoop().run()


if __name__ == "__main__":
    main()
