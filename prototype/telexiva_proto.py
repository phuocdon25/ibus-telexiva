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

    _next_id = 0

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        TelexivaProtoEngine._next_id += 1
        self.iid = TelexivaProtoEngine._next_id   # mỗi input context một engine, để phân biệt trong log
        self.client = "?"
        self.cfg = _load_config()
        self.caps = 0
        self.purpose = IBus.InputPurpose.FREE_FORM
        self.raw = ""     # các phím của từ hiện tại
        self.shown = ""   # chữ engine tin là đang nằm trong ứng dụng cho từ hiện tại
        self.frozen = False  # guard đã chặn: bỏ qua phần còn lại của từ
        self.recent = []  # các giá trị shown trước đó của từ này (ô nhập có thể báo trễ)
        self._log("engine created cfg=%s", self.cfg)

    def _log(self, fmt: str, *args):
        LOG.info("[%d %s] " + fmt, self.iid, self.client, *args)

    # ---- trạng thái ----

    def _reset(self, why: str):
        if self.raw:
            self._log("reset why=%s word_len=%d", why, len(self.shown))
        self.raw = ""
        self.shown = ""
        self.recent = []
        self.frozen = False

    def _set_shown(self, new: str):
        if new != self.shown:
            self.recent = (self.recent + [self.shown])[-2:]
        self.shown = new

    def _new_style(self) -> bool:
        return self.cfg.get("tone") == "new"

    def _has_surrounding(self) -> bool:
        return bool(self.caps & IBus.Capabilite.SURROUNDING_TEXT)

    def _strategy(self) -> str:
        s = self.cfg.get("strategy", "auto")
        if s in ("s2", "s3", "s3k"):
            return s
        if self.purpose == IBus.InputPurpose.TERMINAL:
            return "s3"   # terminal tự khai báo (ví dụ VTE): không tin surrounding text
        if self._has_surrounding():
            return "s2"
        # Ghi chú thử nghiệm (Chrome XWayland, gtk3-im): s3 bị đảo thứ tự Backspace/commit
        # (taoj -> "taạ"); s3k (gửi cả chữ bằng phím) thì Chrome bỏ qua keysym có dấu
        # (taoj -> "to"). Cả hai không dùng được; s3k chỉ còn là tùy chọn thử nghiệm.
        return "s3"

    # ---- guard ----

    def _guard_ok(self) -> bool:
        """Chữ ngay trước con trỏ có đúng là self.shown không."""
        mode = self.cfg.get("guard", "strict")
        if mode == "off" or not self._has_surrounding():
            return True
        text, cursor, anchor = self.get_surrounding_text()
        full = text.get_text() if text else ""
        before = full[:cursor]
        # - Bôi đen phía SAU con trỏ (inline autocomplete của omnibox) không ảnh hưởng: cho qua.
        # - Khi gõ nhanh, ô nhập có thể báo surrounding text trễ 1–2 phím: chấp nhận
        #   cả các trạng thái shown gần nhất.
        candidates = [c for c in [self.shown] + self.recent if c] or [""]
        ok = anchor >= cursor and any(before.endswith(c) for c in candidates)
        if not ok and anchor != cursor:
            # Một số client (VS Code/Electron trên GNOME Wayland) báo cursor và anchor lệch
            # nhau đúng bằng số byte dư của chữ có dấu, dù không có vùng chọn. Thử đối chiếu
            # theo anchor; log lại để kiểm chứng giả thuyết (không ghi nội dung).
            if any(full[:anchor].endswith(c) for c in candidates):
                self._log("guard matched_by=anchor cursor=%d anchor=%d shown_len=%d utf8_extra=%d",
                          cursor, anchor, len(self.shown),
                          len(self.shown.encode("utf-8")) - len(self.shown))
                return True
        if not ok:
            # Mặc định chỉ log độ dài và vị trí, không log nội dung.
            self._log("guard mismatch mode=%s before_len=%d cursor=%d anchor=%d shown_len=%d",
                     mode, len(before), cursor, anchor, len(self.shown))
            self._log("guard diag %s", self._diag(full, cursor, anchor))
            if self.cfg.get("debug_text") == "yes":
                # CHỈ bật tạm thời khi người dùng đồng ý, để chẩn đoán lỗi guard.
                lo, hi = max(0, min(cursor, anchor) - 20), max(cursor, anchor) + 20
                self._log("DEBUG_TEXT window=%r cursor_in_window=%d anchor_in_window=%d "
                          "shown=%r recent=%r full_len=%d utf8_len=%d",
                          full[lo:hi], cursor - lo, anchor - lo, self.shown, self.recent,
                          len(full), len(full.encode("utf-8")))
        return ok or mode == "log"

    def _diag(self, full: str, cursor: int, anchor: int) -> str:
        """Mô tả bằng CON SỐ (không chứa chữ) vị trí của từ đang gõ trong surrounding text.

        end_rel_cursor = vị trí kết thúc của lần xuất hiện gần con trỏ nhất, trừ cursor.
        Ví dụ +3 nghĩa là từ đang gõ thật ra kết thúc ở cursor+3.
        """
        import unicodedata
        parts = []
        for label, word in [("shown", self.shown)] + [(f"recent{i}", w) for i, w in enumerate(self.recent)]:
            if not word:
                continue
            hits = []
            start = full.find(word)
            while start != -1:
                hits.append(start + len(word))
                start = full.find(word, start + 1)
            if hits:
                end = min(hits, key=lambda e: abs(e - cursor))
                parts.append(f"{label}:found={len(hits)} end_rel_cursor={end - cursor:+d} "
                             f"end_rel_anchor={end - anchor:+d}")
            else:
                nfd = unicodedata.normalize("NFD", word) in unicodedata.normalize("NFD", full)
                parts.append(f"{label}:found=0 nfd_found={nfd}")
        parts.append(f"full_len={len(full)} cursor_ok={0 <= cursor <= len(full)}")
        return " | ".join(parts)

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
                    self._forward_key(IBus.KEY_BackSpace, KEYCODE_BACKSPACE)
        if ins:
            if strategy == "s3k":
                for c in ins:
                    self._forward_key(IBus.unicode_to_keyval(c), 0)
            else:
                self.commit_text(IBus.Text.new_from_string(ins))
        self._set_shown(new)
        self._log("replace strategy=%s del=%d ins=%d", strategy, n_del, len(ins))
        return True

    def _forward_key(self, keyval: int, keycode: int):
        self.forward_key_event(keyval, keycode, 0)
        self.forward_key_event(keyval, keycode, IBus.ModifierType.RELEASE_MASK)

    def _finish_word(self, why: str):
        """Kết thúc từ: khôi phục phím gốc nếu sai chính tả."""
        if self.raw:
            final = finalize(self.raw, self._new_style())
            if final != self.shown:
                self._log("finalize restore")
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

        if self.frozen:
            return False

        raw = self.raw + ch
        new = transform(raw, self._new_style())

        if new == self.shown + ch:
            # Không biến đổi: để ứng dụng tự chèn phím, giống English.
            self.raw = raw
            self._set_shown(new)
            return False

        if self._replace(new):
            self.raw = raw
            return True

        # Guard chặn: không chắc nội dung ô nhập. An toàn nhất là để các phím còn lại
        # của từ này đi thẳng, không biến đổi gì, cho tới khi kết thúc từ.
        self._reset("guard")
        self.frozen = True
        return False

    def do_focus_in(self):
        self._reset("focus_in")
        # Yêu cầu client gửi surrounding text (IBus chỉ gửi khi engine đã hỏi).
        self.get_surrounding_text()
        self._log("focus_in caps=0x%x surrounding=%s strategy=%s purpose=%s",
                 self.caps, self._has_surrounding(), self._strategy(), int(self.purpose))

    def do_focus_out(self):
        self._reset("focus_out")

    # Khi engine được tạo với has_focus_id=True, IBus gọi các hàm *_id kèm tên client
    # (ví dụ "gtk4-im:…", "wayland", "xim") thay cho focus_in/focus_out.
    def do_focus_in_id(self, object_path, client):
        self.client = client or "-"
        self.do_focus_in()

    def do_focus_out_id(self, object_path):
        self.do_focus_out()

    def do_reset(self):
        self._reset("reset")

    def do_enable(self):
        self.get_surrounding_text()
        self._log("enable")

    def do_disable(self):
        self._reset("disable")

    def do_set_capabilities(self, caps):
        self.caps = caps
        self._log("set_capabilities caps=0x%x surrounding=%s", caps, self._has_surrounding())

    def do_set_content_type(self, purpose, hints):
        self.purpose = purpose
        self._log("content_type purpose=%d hints=0x%x", int(purpose), int(hints))

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

    counter = {"n": 0}

    def create_engine(_factory, name):
        # Tự tạo engine để bật has_focus_id (nhận tên client trong focus_in_id).
        counter["n"] += 1
        return TelexivaProtoEngine(
            engine_name=name,
            object_path=f"/org/freedesktop/IBus/Engine/TelexivaProto/{counter['n']}",
            connection=bus.get_connection(),
            has_focus_id=True,
        )

    factory.connect("create-engine", create_engine)

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
