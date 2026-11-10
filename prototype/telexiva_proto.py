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
import time
import sys
from logging.handlers import RotatingFileHandler

import gi

gi.require_version("IBus", "1.0")
from gi.repository import GLib, GObject, IBus  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from telex import _english, finalize, transform  # noqa: E402

ENGINE_NAME = "telexiva-proto"
BUS_NAME = "org.freedesktop.IBus.TelexivaProto"
KEYCODE_BACKSPACE = 14  # evdev

LETTER_EXTRA = set("[]{}")
# Từ đứng ngay sau các ký tự này được coi là code/URL/email: giữ nguyên, không biến đổi
# (foo_bar, api/test, user@host, obj.test, $var, a=test).
CODE_PREV_CHARS = set("_./@:\\$#=~<>")
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
        self.hints = 0
        self.prev_char = ""          # ký tự không phải chữ gần nhất (để nhận ra ngữ cảnh code)
        # Hướng 2: ô bỏ qua delete_surrounding_text (ô soạn thảo nâng cao như ChatGPT, Gemini)
        # -> chuyển sang preedit cho tới khi focus sang ô khác.
        self.preedit_mode = False
        self.pending_verify = None   # kiểm tra lệnh xóa S2 vừa gửi có được áp dụng không
        self.inflight = None         # (chữ sau khi xóa, chưa chèn; thời điểm) của lần sửa gần nhất
        self.last_edit_at = 0.0      # thời điểm lần sửa S2 gần nhất
        self.awaiting_confirm = None # thời điểm gửi lần sửa chưa được ô nhập xác nhận
        self.waiting = False         # đang đợi ô nhập xác nhận (vòng lặp sự kiện lồng nhau)
        self.key_queue = []          # phím đến trong lúc đợi, xử lý lại theo thứ tự
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
        self.inflight = None

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
        if s in ("s1", "s2", "s3", "s3k"):
            return s
        if self.preedit_mode:
            return "s1"
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
        candidates = [c for c in [self.shown] + self.recent if c]
        # Ngay sau một lần sửa, ô nhập có thể báo trạng thái "đã xóa, chưa chèn"
        # (xuoongs: báo "xu" trong khi engine đã gửi "xuôn"). Chấp nhận trong 0.5 giây.
        if self.inflight and time.monotonic() - self.inflight[1] < 0.5 and self.inflight[0]:
            candidates.append(self.inflight[0])
        candidates = candidates or [""]
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
        if n_del and self._strategy() == "s2":
            self._wait_confirm()
        if n_del and not self._guard_ok():
            return False
        if n_del:
            self.inflight = (old[:p], time.monotonic())
        strategy = self._strategy()
        if n_del:
            if strategy == "s2":
                n_chars = self._mutter_safe_delete_count(old[p:])
                self.delete_surrounding_text(-n_chars, n_chars)
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
        if strategy == "s2" and n_del:
            # Ô bỏ qua lệnh xóa sẽ cho ra: chữ cũ + phần chèn (taoj -> "tao" + "ạo").
            now = time.monotonic()
            self.pending_verify = {"expect": new, "broken": old + ins, "tries": 3,
                                   "gap_ms": (now - self.last_edit_at) * 1000}
            self.last_edit_at = now
            self.awaiting_confirm = now
        self._log("replace strategy=%s del=%d ins=%d", strategy, n_del, len(ins))
        return True

    def _code_context(self) -> bool:
        """Ký tự ngay trước từ mới có phải ký tự code (_ . / @ …) không."""
        prev = self.prev_char
        if not prev and self._has_surrounding():
            text, cursor, _ = self.get_surrounding_text()
            prev = (text.get_text() if text else "")[:cursor][-1:]
        return prev in CODE_PREV_CHARS

    def _check_pending_verify(self):
        """Ở phím kế tiếp: xem lệnh xóa S2 trước đó có được ô nhập áp dụng không."""
        pv = self.pending_verify
        if not pv or not self._has_surrounding():
            self.pending_verify = None
            return
        text, cursor, anchor = self.get_surrounding_text()
        full = text.get_text() if text else ""
        befores = {full[:cursor], full[:anchor]}
        if any(b.endswith(pv["expect"]) for b in befores):
            self.pending_verify = None
            return
        if any(b.endswith(pv["broken"]) for b in befores):
            self.pending_verify = None
            if pv["gap_ms"] < 150:
                # Hai lần sửa quá sát nhau: ô chưa xử lý xong lần trước nên bỏ lệnh xóa.
                # Đây là "va chạm thời gian", không phải ô kiểu ChatGPT: không chuyển sang nháp.
                self._log("s2_race gap_ms=%.0f (không chuyển sang nháp)", pv["gap_ms"])
                self._reset("s2_race")
                return
            self.preedit_mode = True
            # purpose/hints là "dấu vân tay" của ô, để sau này nhận diện trước (Bước 3).
            self._log("s2_ignored -> preedit purpose=%d hints=0x%x", int(self.purpose), self.hints)
            self._reset("s2_ignored")
            return
        pv["tries"] -= 1
        if pv["tries"] <= 0:
            self.pending_verify = None

    # ---- preedit (S1) ----

    def _show_preedit(self):
        text = transform(self.raw, self._new_style())
        t = IBus.Text.new_from_string(text)
        t.append_attribute(IBus.AttrType.UNDERLINE, IBus.AttrUnderline.SINGLE, 0, len(text))
        # COMMIT: khi ô mất focus, IBus tự chốt phần nháp (giống ibus-unikey).
        self.update_preedit_text_with_mode(t, len(text), True, IBus.PreeditFocusMode.COMMIT)
        self.shown = text

    def _commit_preedit(self, final: bool):
        if self.raw:
            text = finalize(self.raw, self._new_style()) if final else transform(self.raw, self._new_style())
            self.hide_preedit_text()
            self.commit_text(IBus.Text.new_from_string(text))
        self.raw = ""
        self.shown = ""

    def _process_preedit(self, keyval, ch: str, is_letter: bool) -> bool:
        if is_letter:
            self.raw += ch
            self._show_preedit()
            return True
        if keyval == IBus.KEY_BackSpace and self.raw:
            # Xóa một ký tự đang hiển thị: bỏ phím cuối cho tới khi chữ ngắn đi.
            target = self.shown[:-1]
            popped = []
            while self.raw and len(transform(self.raw, self._new_style())) >= len(self.shown):
                popped.insert(0, self.raw[-1])
                self.raw = self.raw[:-1]
            # Giữ lại dấu/biến đổi của phần còn lại: tạo + Backspace -> tạ (không phải ta).
            for k in popped:
                if transform(self.raw + k, self._new_style()) == target:
                    self.raw += k
                    break
            if self.raw:
                self._show_preedit()
            else:
                self.hide_preedit_text()
                self.shown = ""
            return True
        if keyval == IBus.KEY_Escape and self.raw:
            self._commit_preedit(final=False)
            return False
        # Kết thúc từ, phím điều hướng, phím khác: chốt nháp rồi cho phím đi tiếp.
        self._commit_preedit(final=True)
        return False

    def _mutter_safe_delete_count(self, to_delete: str):
        """Số KÝ TỰ cần gửi trong delete_surrounding_text để xóa đúng `to_delete`.

        Trên GNOME Wayland, Mutter đổi số ký tự sang số BYTE bằng bản sao surrounding text
        của nó, rồi Chrome xóa theo byte. Nếu bản sao còn cũ (chưa có lần sửa trước) thì số
        byte bị tính sai; khi điểm cắt rơi vào giữa một ký tự UTF-8, Chrome bỏ qua cả lệnh
        xóa (gocs + o -> "gócốc"). Engine thấy đúng bản sao đó, nên chọn số ký tự k sao cho
        k ký tự cuối của bản sao có cùng số byte với phần cần xóa thật.
        """
        if not self._has_surrounding():
            return len(to_delete)
        text, cursor, _ = self.get_surrounding_text()
        view = (text.get_text() if text else "")[:cursor]
        if view.endswith(to_delete):
            return len(to_delete)          # bản sao đã mới: không cần bù
        if self.inflight and self.inflight[0] and view.endswith(self.inflight[0]):
            return len(to_delete)          # Mutter đang cập nhật dở ("đã xóa, chưa chèn")
        if not any(r and view.endswith(r) for r in self.recent):
            return len(to_delete)          # không nhận ra bản sao: giữ cách cũ (guard đã cho qua)
        # Bản sao là một trạng thái cũ hoàn chỉnh của từ: bù theo byte.
        want = len(to_delete.encode("utf-8"))
        total = 0
        for k in range(1, len(view) + 1):
            total += len(view[-k].encode("utf-8"))
            if total == want:
                self._log("delete_byte_compensated chars=%d->%d bytes=%d", len(to_delete), k, want)
                return k
            if total > want:
                break
        self._log("delete_byte_mismatch want_bytes=%d view_len=%d", want, len(view))
        return len(to_delete)

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
        if self.waiting:
            # Phím đến trong lúc đang đợi xác nhận: giữ lại, xử lý sau đúng thứ tự.
            if state & IBus.ModifierType.RELEASE_MASK:
                return bool(self.key_queue)
            self.key_queue.append((keyval, keycode, state))
            return True
        handled = self._handle_key(keyval, keycode, state)
        self._drain_queue()
        return handled

    def _drain_queue(self):
        while self.key_queue:
            keyval, keycode, state = self.key_queue.pop(0)
            if self._handle_key(keyval, keycode, state):
                continue
            # Phím lẽ ra đi thẳng nhưng đã bị giữ lại: chèn bằng commit (chữ, số, dấu câu).
            ch = IBus.keyval_to_unicode(keyval) or ""
            if len(ch) == 1 and ch.isprintable() and not state & SHORTCUT_MASK:
                self.commit_text(IBus.Text.new_from_string(ch))
            else:
                self.forward_key_event(keyval, keycode, state)
            self._log("queued key replayed passthrough=%s", "commit" if ch.isprintable() else "forward")

    def _wait_confirm(self, max_ms: float = 30.0):
        """Đợi ô nhập xác nhận lần sửa trước (set_surrounding_text), tối đa max_ms.

        Hai lần sửa quá sát nhau (< ~13 ms) làm ô nhập bỏ lệnh xóa thứ hai
        (truongw + o -> "trươnguongwo"). Vòng lặp sự kiện lồng nhau cho phép nhận
        set_surrounding_text; phím đến trong lúc này được xếp hàng (do_process_key_event).
        """
        if self.awaiting_confirm is None:
            return
        if (time.monotonic() - self.awaiting_confirm) * 1000 > 200:
            self.awaiting_confirm = None   # quá cũ: ô nhập không gửi xác nhận, bỏ qua
            return
        start = time.monotonic()
        ctx = GLib.MainContext.default()
        self.waiting = True
        try:
            while self.awaiting_confirm is not None and (time.monotonic() - start) * 1000 < max_ms:
                if not ctx.iteration(False):
                    time.sleep(0.0005)
        finally:
            self.waiting = False
        self._log("wait_confirm waited_ms=%.1f confirmed=%s queued=%d",
                  (time.monotonic() - start) * 1000, self.awaiting_confirm is None, len(self.key_queue))
        self.awaiting_confirm = None

    def _handle_key(self, keyval, keycode, state):
        if state & IBus.ModifierType.RELEASE_MASK:
            return False
        if self.purpose in (IBus.InputPurpose.PASSWORD, IBus.InputPurpose.PIN):
            return False
        if keyval in MODIFIER_KEYVALS:
            return False
        if state & SHORTCUT_MASK:
            if self.preedit_mode and self.raw:
                self._commit_preedit(final=True)
            self._reset("shortcut")
            return False

        ch = IBus.keyval_to_unicode(keyval) or ""   # PyGObject trả về str
        is_letter = len(ch) == 1 and ch.isascii() and (ch.isalpha() or ch in LETTER_EXTRA)

        if self.pending_verify:
            self._check_pending_verify()
        if not is_letter:
            self.prev_char = ch if len(ch) == 1 and ch.isprintable() else ""
        elif not self.raw and not self.frozen and self._code_context():
            self.frozen = True
            self._log("code_context -> giữ nguyên từ")
        if self.frozen and is_letter:
            return False

        if self._strategy() == "s1":
            return self._process_preedit(keyval, ch, is_letter)

        if not is_letter:
            if ch == "@" and self.raw and self.shown != self.raw and not self._strategy() == "s1":
                # Phần trước @ của email không bao giờ có dấu tiếng Việt: test@ -> giữ "test".
                self._log("email_local_part -> khôi phục phím gốc")
                self._replace(self.raw)
                self._reset("email")
            elif keyval in WORD_END_KEYVALS or (len(ch) == 1 and ch.isprintable()):
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
            if self.pending_verify:
                self.pending_verify["expect"] += ch
                self.pending_verify["broken"] += ch
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
        self.prev_char = ""
        if self.preedit_mode:
            self._log("preedit_mode off (focus changed)")
        self.preedit_mode = False      # ô mới: thử lại không nháp
        self.pending_verify = None
        # Yêu cầu client gửi surrounding text (IBus chỉ gửi khi engine đã hỏi).
        self.get_surrounding_text()
        self._log("focus_in caps=0x%x surrounding=%s strategy=%s purpose=%s hints=0x%x",
                 self.caps, self._has_surrounding(), self._strategy(), int(self.purpose), self.hints)

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
        self.hints = int(hints)
        self._log("content_type purpose=%d hints=0x%x", int(purpose), int(hints))

    def do_set_surrounding_text(self, text, cursor_pos, anchor_pos):
        # Ô nhập gửi nội dung mới -> đo thời gian từ lần sửa gần nhất (chỉ ghi số).
        if self.awaiting_confirm is not None:
            self._log("confirm_ms=%.1f", (time.monotonic() - self.awaiting_confirm) * 1000)
            self.awaiting_confirm = None
        IBus.Engine.do_set_surrounding_text(self, text, cursor_pos, anchor_pos)

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

    LOG.info("started argv=%s english_words=%d", sys.argv[1:], len(_english()))  # nạp sẵn từ điển
    GLib.MainLoop().run()


if __name__ == "__main__":
    main()
