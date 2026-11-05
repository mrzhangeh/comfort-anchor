# -*- coding: utf-8 -*-
"""静锚 ComfortAnchor - 桌面游戏晕动症舒适叠加层（主程序 / 控制面板 / CLI）。

v2 变更：
  1. 控制面板改为可滚动 + 固定底栏，按 DPI 缩放字体与窗口，任何缩放下都不截断。
  2. 提供 11 种参照图形，默认「无标记 + 1px 静止边框」，把画面污染降到最低；
     加入中央透明区与四角 HUD 避让区，避免遮挡小地图 / 技能栏。
  3. 循证澄清：Cao 2018 的 dynamic rest frame 是「不透明度随运动强度变化」，
     不是位置移动。默认仍为绝对静止；明度自适应 / 反向光流微动为可选实验模式。

循证背景见 README.md 与工作区《游戏晕动症循证整理.html》。
本工具是舒适辅助工具，不是医疗设备。
"""
from __future__ import annotations

import os
import platform
import sys
import traceback

from PIL import Image

import ca_config as C
from ca_config import (APP_TITLE, HOTKEY_HELP, MARK_COLOR_LABELS, MOTION_LABELS,
                       MOTION_MODES, MOTION_NOTES, PATTERN_IDS, PRESET_LABELS,
                       PRESETS, VERSION, apply_preset, clamp, load_config,
                       log_path, sanitize, save_config)
from ca_render import (MARK_PAD, PATTERNS, PATTERN_BY_ID, PATTERN_LABELS,
                       mock_game_frame, pattern_sheet, render_frame,
                       render_marks, render_overlay, to_bgra_premultiplied)
from ca_win32 import IS_WINDOWS, InputSampler, OverlayWindow, list_monitors, system_dpi

if IS_WINDOWS:
    import ca_win32


# ---------------------------------------------------------------------------
# 控制面板
# ---------------------------------------------------------------------------

class App:
    def __init__(self, cfg):
        self.cfg = sanitize(cfg)
        self.monitors = list_monitors()
        if self.cfg["monitor_index"] >= len(self.monitors):
            self.cfg["monitor_index"] = 0

        self.frame_win = None
        self.marks_win = None
        self._bound = None
        self.sampler = InputSampler()
        self.redraw_job = None
        self.preview_job = None
        self.level = 0.0
        self.off_x = self.off_y = 0.0
        self.hotkey_state = {"toggle": False, "panel": False, "panic": False, "pattern": False}
        self._syncing = False
        self._preview_photo = None
        self.sliders = {}
        self.checks = {}
        self.combos = {}

        import tkinter as tk
        from tkinter import font as tkfont, ttk
        self.tk, self.ttk = tk, ttk

        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self._setup_dpi(tkfont, ttk)
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(80, self.rebuild)
        self.root.after(220, self._poll_hotkeys)
        self.root.after(260, self._tick_motion)

        if not os.path.exists(C.config_path()):
            self.root.after(600, self._first_run_hint)

    # -- DPI / 布局 ---------------------------------------------------------
    def _setup_dpi(self, tkfont, ttk):
        dpi = system_dpi() if IS_WINDOWS else 96
        self.scale = clamp(dpi / 96.0, 1.0, 2.2)
        s = self.scale
        self.pad = int(round(14 * s))
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont"):
            try:
                tkfont.nametofont(name).configure(size=-int(round(10 * s)))
            except Exception:
                pass
        style = ttk.Style(self.root)
        base = ("Microsoft YaHei UI", -int(round(10 * s)))
        bold = ("Microsoft YaHei UI", -int(round(10 * s)), "bold")
        title = ("Microsoft YaHei UI", -int(round(17 * s)), "bold")
        style.configure(".", font=base)
        style.configure("TLabelframe.Label", font=bold)
        style.configure("Title.TLabel", font=title)
        self.wrap = int(round(470 * s))

        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w = int(round(548 * s))
        # 默认高度按内容量给足，常见缩放档位下无需滚动即可看全；小屏仍可滚动。
        h = min(int(round(900 * s)), max(int(round(460 * s)), sh - int(round(80 * s))))
        self.root.geometry("%dx%d" % (w, h))
        self.root.minsize(int(round(430 * s)), int(round(400 * s)))
        self.root.resizable(True, True)

    def _build_ui(self):
        tk, ttk, p = self.tk, self.ttk, self.pad
        root = self.root

        header = ttk.Frame(root, padding=(p, p, p, 4))
        header.pack(fill="x", side="top")
        ttk.Label(header, text="静锚", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="静止参照框 · 屏幕空间固定 · 与重力对齐 · 默认无动画",
                  foreground="#666666").pack(anchor="w", pady=(2, 0))

        # 固定底栏：无论内容多长，开关与按钮始终可见可点
        footer = ttk.Frame(root, padding=(p, 6, p, 8))
        footer.pack(fill="x", side="bottom")
        actions = ttk.Frame(footer)
        actions.pack(fill="x")
        self.enabled_var = tk.BooleanVar(value=self.cfg["enabled"])
        ttk.Checkbutton(actions, text="启用叠加层", variable=self.enabled_var,
                        command=lambda: self.set_enabled(self.enabled_var.get())
                        ).pack(side="left")
        ttk.Button(actions, text="隐藏面板", command=self.hide_panel).pack(side="right", padx=(6, 0))
        ttk.Button(actions, text="退出", command=self.on_close).pack(side="right")
        self.status_var = tk.StringVar(value="")
        ttk.Label(footer, textvariable=self.status_var, foreground="#444444",
                  wraplength=self.wrap, justify="left").pack(fill="x", pady=(6, 0))
        ttk.Label(footer, text=HOTKEY_HELP, foreground="#777777",
                  wraplength=self.wrap, justify="left").pack(fill="x", pady=(2, 0))

        outer = ttk.Frame(root)
        outer.pack(fill="both", expand=True, side="top")
        canvas = tk.Canvas(outer, highlightthickness=0, bd=0)
        scroll = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        content = ttk.Frame(canvas, padding=(p, 4, p, p))
        self._canvas = canvas
        self._win_id = canvas.create_window((0, 0), window=content, anchor="nw")
        content.bind("<Configure>",
                     lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(self._win_id, width=e.width))

        def on_wheel(event):
            if canvas.yview() != (0.0, 1.0):
                canvas.yview_scroll(int(-event.delta / 120) * 2, "units")
        canvas.bind_all("<MouseWheel>", on_wheel)

        self._section_presets(content)
        self._section_pattern(content)
        self._section_sliders(content)
        self._section_switches(content)
        self._section_options(content)
        self._section_note(content)
        self._sync_widgets()

    # -- 各分区 -------------------------------------------------------------
    def _section_presets(self, parent):
        ttk = self.ttk
        box = ttk.LabelFrame(parent, text="① 预设", padding=10)
        box.pack(fill="x", pady=(6, 6))
        row = ttk.Frame(box)
        row.pack(fill="x")
        for key in ("minimal", "gentle", "standard", "strong"):
            ttk.Button(row, text=PRESET_LABELS[key], width=11,
                       command=lambda k=key: self.on_preset(k)).pack(side="left", padx=(0, 6))
        ttk.Label(box, text="默认「极简」只有 1px 边框与四角刻线，几乎不改变画面。"
                           "Baek & Kim 2025 发现参照框密度变化对减晕与临场感均无显著影响，"
                           "因此效果相近时应优先选遮挡最少的配置。",
                  foreground="#666666", wraplength=self.wrap, justify="left"
                  ).pack(anchor="w", pady=(8, 0))

    def _section_pattern(self, parent):
        tk, ttk = self.tk, self.ttk
        box = ttk.LabelFrame(parent, text="② 参照图形", padding=10)
        box.pack(fill="x", pady=6)
        top = ttk.Frame(box)
        top.pack(fill="x")
        ttk.Label(top, text="形状").pack(side="left", padx=(0, 8))
        self.pattern_var = tk.StringVar()
        cb = ttk.Combobox(top, textvariable=self.pattern_var, state="readonly", width=26,
                          values=[PATTERN_LABELS[i] for i in PATTERN_IDS])
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", self.on_pattern)
        self.combos["pattern"] = cb
        ttk.Button(top, text="下一个 (P)", command=self.cycle_pattern).pack(side="left", padx=(8, 0))

        inner = ttk.Frame(box)
        inner.pack(fill="x", pady=(8, 0))
        self.pattern_note = ttk.Label(inner, text="", foreground="#555555",
                                      wraplength=int(self.wrap * 0.60), justify="left")
        self.pattern_note.pack(side="left", fill="x", expand=True)
        self.preview_label = ttk.Label(inner, text="预览")
        self.preview_label.pack(side="right", padx=(8, 0))

    SLIDERS = (
        ("opacity", "标记不透明度 (%)", 0, 40),
        ("size", "图形尺寸 / 线宽 (px)", 1, 12),
        ("density", "图形密度 (%)", 0, 80),
        ("vignette", "周边暗角 (%)", 0, 20),
        ("inner_clear", "中央透明区 (%)", 25, 85),
        ("hud_guard", "四角 HUD 避让 (%)", 0, 25),
        ("drift_gain", "微动幅度 (px)", 0, 12),
    )

    def _section_sliders(self, parent):
        tk, ttk = self.tk, self.ttk
        box = ttk.LabelFrame(parent, text="③ 视觉参数", padding=10)
        box.pack(fill="x", pady=6)
        for key, label, lo, hi in self.SLIDERS:
            row = ttk.Frame(box)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=label, width=23).pack(side="left")
            var = tk.IntVar(value=self.cfg[key])
            scale = ttk.Scale(row, from_=lo, to=hi, variable=var, orient="horizontal",
                              command=lambda v, k=key: self.on_slide(k))
            scale.pack(side="left", fill="x", expand=True)
            value_label = ttk.Label(row, text=str(self.cfg[key]), width=4)
            value_label.pack(side="right")
            self.sliders[key] = (var, value_label)

    CHECKS = (
        ("show_border", "静止细边框（1px，与重力对齐）"),
        ("show_ticks", "四角刻线"),
        ("show_horizon", "中央断开的水平参考线"),
        ("show_crosshair", "中央准星（对照实验未显示减晕优势，默认关）"),
    )

    def _section_switches(self, parent):
        tk, ttk = self.tk, self.ttk
        box = ttk.LabelFrame(parent, text="④ 元素开关", padding=10)
        box.pack(fill="x", pady=6)
        for key, label in self.CHECKS:
            var = tk.BooleanVar(value=self.cfg[key])
            ttk.Checkbutton(box, text=label, variable=var,
                            command=lambda k=key, v=var: self.on_check(k, v)
                            ).pack(anchor="w", pady=1)
            self.checks[key] = var

    def _section_options(self, parent):
        tk, ttk = self.tk, self.ttk
        box = ttk.LabelFrame(parent, text="⑤ 显示器 / 颜色 / 运动模式", padding=10)
        box.pack(fill="x", pady=6)

        mon_names = ["%d: %dx%d @ (%d,%d)%s" % (
            i + 1, m["width"], m["height"], m["left"], m["top"],
            " [主]" if m["primary"] else "") for i, m in enumerate(self.monitors)]
        self.mon_names = mon_names
        self.mon_var = tk.StringVar(value=mon_names[self.cfg["monitor_index"]])
        self.color_var = tk.StringVar(
            value=MARK_COLOR_LABELS.get(self.cfg["mark_color"], MARK_COLOR_LABELS["neutral"]))
        self.motion_var = tk.StringVar(value=MOTION_LABELS[self.cfg["motion_mode"]])

        for r, label, var, values, handler in (
            (0, "显示器", self.mon_var, mon_names, self.on_monitor),
            (1, "标记颜色", self.color_var, list(MARK_COLOR_LABELS.values()), self.on_color),
            (2, "运动模式", self.motion_var, [MOTION_LABELS[m] for m in MOTION_MODES], self.on_motion),
        ):
            ttk.Label(box, text=label).grid(row=r, column=0, sticky="w", padx=(0, 8), pady=3)
            cb = ttk.Combobox(box, textvariable=var, values=values,
                              state="readonly", width=34)
            cb.grid(row=r, column=1, sticky="w", pady=3)
            cb.bind("<<ComboboxSelected>>", handler)

        self.motion_note = ttk.Label(box, text="", foreground="#555555",
                                     wraplength=self.wrap, justify="left")
        self.motion_note.grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))

    def _section_note(self, parent):
        ttk = self.ttk
        ttk.Label(parent,
                  text="舒适辅助工具，不是医疗设备。出现恶心、头晕请按 F9 并停止游戏休息。\n"
                       "不注入游戏、不截屏、不联网、无遥测；独占全屏请改为无边框 / 窗口化全屏。\n"
                       "实验性运动模式仅用只读的鼠标位移 / 按键状态估计，raw input 锁光标的游戏可能不生效。",
                  foreground="#777777", wraplength=self.wrap, justify="left"
                  ).pack(fill="x", pady=(10, 4))

    # -- UI 同步 ------------------------------------------------------------
    def _sync_widgets(self):
        self._syncing = True
        try:
            for key, (var, label) in self.sliders.items():
                var.set(self.cfg[key])
                label.config(text=str(self.cfg[key]))
            for key, var in self.checks.items():
                var.set(self.cfg[key])
            self.enabled_var.set(self.cfg["enabled"])
            self.pattern_var.set(PATTERN_LABELS[self.cfg["pattern"]])
            self.motion_var.set(MOTION_LABELS[self.cfg["motion_mode"]])
            self.color_var.set(MARK_COLOR_LABELS[self.cfg["mark_color"]])
            self.mon_var.set(self.mon_names[self.cfg["monitor_index"]])
            self.pattern_note.config(text=PATTERN_BY_ID[self.cfg["pattern"]].note)
            self.motion_note.config(text=MOTION_NOTES[self.cfg["motion_mode"]])
            self._update_preview()
        finally:
            self._syncing = False

    def _update_preview(self):
        try:
            from PIL import ImageTk
        except ImportError:
            return
        try:
            w, h = 244, 138
            layer = render_overlay(w, h, self.cfg)
            img = Image.alpha_composite(mock_game_frame(w, h), layer).convert("RGB")
            self._preview_photo = ImageTk.PhotoImage(img)
            self.preview_label.configure(image=self._preview_photo, text="")
        except Exception:
            pass

    def _update_status(self):
        mon = self.monitors[self.cfg["monitor_index"]]
        state = "已启用" if self.cfg["enabled"] else "已关闭"
        self.status_var.set("%s · %dx%d @ %d%% 缩放 · %s · %s · %s" % (
            state, mon["width"], mon["height"], int(self.scale * 100),
            PRESET_LABELS.get(self.cfg["preset"], "自定义"),
            PATTERN_LABELS[self.cfg["pattern"]],
            MOTION_LABELS[self.cfg["motion_mode"]]))

    # -- 事件 ---------------------------------------------------------------
    def _schedule(self):
        if self.redraw_job:
            self.root.after_cancel(self.redraw_job)
        self.redraw_job = self.root.after(170, self.rebuild)
        if self.preview_job:
            self.root.after_cancel(self.preview_job)
        self.preview_job = self.root.after(220, self._update_preview)

    def _mark_custom(self):
        self.cfg["preset"] = "custom"

    def on_slide(self, key):
        if self._syncing:
            return
        var, label = self.sliders[key]
        value = int(round(float(var.get())))
        self.cfg[key] = value
        label.config(text=str(value))
        self._mark_custom()
        self._schedule()

    def on_check(self, key, var):
        if self._syncing:
            return
        self.cfg[key] = bool(var.get())
        self._mark_custom()
        self._schedule()

    def on_preset(self, key):
        apply_preset(self.cfg, key)
        self._sync_widgets()
        self.rebuild()

    def on_pattern(self, _event=None):
        if self._syncing:
            return
        label = self.pattern_var.get()
        pid = next((k for k, v in PATTERN_LABELS.items() if v == label), "none")
        self.cfg["pattern"] = pid
        self._mark_custom()
        self.pattern_note.config(text=PATTERN_BY_ID[pid].note)
        self._update_status()
        self._schedule()

    def cycle_pattern(self):
        idx = PATTERN_IDS.index(self.cfg["pattern"])
        self.cfg["pattern"] = PATTERN_IDS[(idx + 1) % len(PATTERN_IDS)]
        self._mark_custom()
        self._sync_widgets()
        self._update_status()
        self.rebuild()

    def on_monitor(self, _event=None):
        if self._syncing:
            return
        try:
            self.cfg["monitor_index"] = self.mon_names.index(self.mon_var.get())
        except ValueError:
            return
        self.rebuild()

    def on_color(self, _event=None):
        if self._syncing:
            return
        label = self.color_var.get()
        self.cfg["mark_color"] = next(
            (k for k, v in MARK_COLOR_LABELS.items() if v == label), "neutral")
        self._mark_custom()
        self._schedule()

    def on_motion(self, _event=None):
        if self._syncing:
            return
        label = self.motion_var.get()
        self.cfg["motion_mode"] = next(
            (k for k, v in MOTION_LABELS.items() if v == label), "static")
        self.motion_note.config(text=MOTION_NOTES[self.cfg["motion_mode"]])
        self.level = 0.0
        self.off_x = self.off_y = 0.0
        if self.marks_win:
            self.marks_win.set_fade(255)
            self.marks_win.set_offset(0, 0)
        self._update_status()
        self._schedule()

    # -- 叠加层 -------------------------------------------------------------
    def rebuild(self):
        self.redraw_job = None
        save_config(self.cfg)
        mon = self.monitors[self.cfg["monitor_index"]]
        w, h = mon["width"], mon["height"]
        try:
            frame = render_frame(w, h, self.cfg)
            marks = render_marks(w + 2 * MARK_PAD, h + 2 * MARK_PAD, self.cfg)
            signature = (self.cfg["monitor_index"], w, h)
            if self.frame_win and self.marks_win and self._bound == signature:
                self.frame_win.set_image(frame)
                self.marks_win.set_image(marks)
            else:
                self._destroy_windows()
                self.frame_win = OverlayWindow(w, h, mon["left"], mon["top"])
                self.frame_win.set_image(frame)
                self.marks_win = OverlayWindow(
                    w + 2 * MARK_PAD, h + 2 * MARK_PAD,
                    mon["left"] - MARK_PAD, mon["top"] - MARK_PAD)
                self.marks_win.set_image(marks)
                self._bound = signature
            self.set_enabled(self.cfg["enabled"], persist=False)
            self._update_status()
        except Exception as exc:
            from tkinter import messagebox
            messagebox.showerror("叠加层错误", str(exc))

    def _destroy_windows(self):
        for win in (self.marks_win, self.frame_win):
            if win:
                try:
                    win.destroy()
                except Exception:
                    pass
        self.frame_win = self.marks_win = None
        self._bound = None

    def set_enabled(self, value, persist=True):
        self.cfg["enabled"] = bool(value)
        self.enabled_var.set(self.cfg["enabled"])
        for win in (self.frame_win, self.marks_win):
            if win:
                if self.cfg["enabled"]:
                    win.show()
                else:
                    win.hide()
        if persist:
            save_config(self.cfg)
        self._update_status()

    def toggle_enabled(self):
        self.set_enabled(not self.cfg["enabled"])

    def hide_panel(self):
        self.root.withdraw()

    def show_panel(self):
        self.root.deiconify()
        self.root.lift()

    def panic(self):
        self.set_enabled(False)

    def on_close(self):
        save_config(self.cfg)
        self._destroy_windows()
        self.root.destroy()

    # -- 热键（只读轮询） ---------------------------------------------------
    def _pressed(self, vk):
        if not IS_WINDOWS:
            return False
        return bool(ca_win32.user32.GetAsyncKeyState(vk) & 0x8000)

    def _poll_hotkeys(self):
        ctrl, alt = self._pressed(0x11), self._pressed(0x12)
        d = ctrl and alt and self._pressed(ord("D"))
        s = ctrl and alt and self._pressed(ord("S"))
        pkey = ctrl and alt and self._pressed(ord("P"))
        f9 = self._pressed(0x78)
        if d and not self.hotkey_state["toggle"]:
            self.toggle_enabled()
        if s and not self.hotkey_state["panel"]:
            self.show_panel() if self.root.state() != "normal" else self.hide_panel()
        if pkey and not self.hotkey_state["pattern"]:
            self.cycle_pattern()
        if f9 and not self.hotkey_state["panic"]:
            self.panic()
        self.hotkey_state.update(toggle=d, panel=s, pattern=pkey, panic=f9)
        self.root.after(110, self._poll_hotkeys)

    # -- 运动模式循环 -------------------------------------------------------
    def _tick_motion(self):
        mode = self.cfg["motion_mode"]
        fade, off_x, off_y = 255, 0, 0
        if mode != "static" and self.marks_win:
            activity, nx, ny = self.sampler.sample()
            rate = 0.35 if activity > self.level else 0.10
            self.level += (activity - self.level) * rate
            if self.level < 0.008:
                self.level = 0.0
            if mode == "adaptive":
                fade = int((55 + 200 * self.level) // 8 * 8)
            else:
                sign = 1 if mode == "counter" else -1
                gain = self.cfg["drift_gain"]
                tx = sign * nx * gain * self.level
                ty = sign * ny * gain * self.level
                self.off_x += (tx - self.off_x) * 0.25
                self.off_y += (ty - self.off_y) * 0.25
                if abs(self.off_x) < 0.4:
                    self.off_x = 0.0
                if abs(self.off_y) < 0.4:
                    self.off_y = 0.0
                off_x, off_y = int(round(self.off_x)), int(round(self.off_y))
            try:
                self.marks_win.set_fade(fade)
                self.marks_win.set_offset(off_x, off_y)
            except Exception:
                pass
        self.root.after(50, self._tick_motion)

    def _first_run_hint(self):
        from tkinter import messagebox
        messagebox.showinfo(
            "使用提示",
            "静锚默认只画一圈 1px 静止边框 + 四角刻线，几乎不改变游戏画面。\n\n"
            "在「② 参照图形」里可切换 11 种形状，右侧有实时预览，"
            "游戏中按 Ctrl+Alt+P 可逐个试。\n\n"
            "游戏请设为无边框 / 窗口化全屏；独占全屏可能盖住叠加层。\n"
            "出现任何不适请按 F9 立即关闭，并停止游戏休息。")

    def run(self):
        self.root.mainloop()


def build_app(cfg):
    """兼容旧版自检脚本的工厂函数。"""
    return App(cfg).root


# ---------------------------------------------------------------------------
# 自检 / 预览 / 对照表
# ---------------------------------------------------------------------------

def _alpha_stats(alpha):
    """返回 (平均 alpha, 有效墨迹覆盖率%)。

    阈值取 16/255：低于它的 1~3% 暗角属于视觉上不可察觉的渐变，
    会计入「遮挡」纯属指标噪声；真正会盖住游戏信息的是 >=16 的像素。
    """
    hist = alpha.histogram()
    total = float(alpha.width * alpha.height)
    mean = sum(i * count for i, count in enumerate(hist)) / total
    coverage = 100.0 * sum(hist[16:]) / total
    return mean, coverage


def _preset_stats(w, h, key):
    cfg = dict(C.DEFAULTS)
    cfg.update(PRESETS[key])
    alpha = render_overlay(w, h, cfg).getchannel("A")
    mean, coverage = _alpha_stats(alpha)
    center = sum(alpha.crop((w // 2 - 60, h // 2 - 60,
                             w // 2 + 60, h // 2 + 60)).getdata()) / 14400.0
    return cfg, alpha, mean, coverage, center


def selftest(out_path="preview.png"):
    w, h = 1280, 720
    # 预览用「柔和 + 中等密度」以便肉眼看到稀疏圆点；数值断言用默认极简档。
    demo = dict(C.DEFAULTS)
    demo.update(PRESETS["gentle"])
    demo.update({"pattern": "dots", "opacity": 12, "density": 30})
    composed = Image.alpha_composite(mock_game_frame(w, h), render_overlay(w, h, demo)).convert("RGB")
    composed.save(out_path)
    print("preview:", os.path.abspath(out_path), "(demo config: gentle + sparse dots)")
    print("size: %dx%d" % (w, h))
    print("")
    print("%-9s %12s %12s %12s" % ("preset", "mean alpha", "ink >=16", "center"))

    edge = None
    results = {}
    for key in ("minimal", "gentle", "standard", "strong"):
        cfg, alpha, mean, coverage, center = _preset_stats(w, h, key)
        results[key] = (mean, coverage, center)
        print("%-9s %12.3f %11.2f%% %12.3f" % (key, mean, coverage, center))
        if key == "standard":
            edge = alpha.crop((0, 0, 140, 140))
    print("")
    print("edge has marks    :", edge.getbbox() is not None)

    failures = []
    for pattern in PATTERNS:
        one = dict(demo)
        one["pattern"] = pattern.id
        try:
            to_bgra_premultiplied(render_overlay(480, 270, one))
        except Exception as exc:
            failures.append("%s: %s" % (pattern.id, exc))
    print("patterns rendered : %d/%d" % (len(PATTERNS) - len(failures), len(PATTERNS)))
    if failures:
        print("failures:", "; ".join(failures))

    m_mean, m_cov, m_center = results["minimal"]
    s_mean, s_cov, s_center = results["standard"]
    ok = (
        m_center < 1.0 and s_center < 1.0,          # 中央完全透明
        m_mean < 1.0 and m_cov < 2.0,               # 默认档近乎零遮挡
        s_mean < 8.0 and s_cov < 8.0,               # 标准档仍然很淡
        edge.getbbox() is not None,                  # 周边确实有参照物
        not failures,
    )
    passed = all(ok)
    print("checks:", ok)
    print("selftest:", "PASS" if passed else "FAIL")
    return 0 if passed else 1


def make_sheet(out_path="patterns.png"):
    cfg = dict(C.DEFAULTS)
    cfg.update(PRESETS["gentle"])
    sheet = pattern_sheet(cfg)
    sheet.save(out_path)
    print("sheet:", os.path.abspath(out_path), "%dx%d" % sheet.size)
    return 0


def uicheck(out_path="ui_check.txt"):
    """构建完整控制面板（含实时预览）并创建叠加层，用于验证打包后的 exe。"""
    lines = ["ComfortAnchor %s UI" % VERSION]
    try:
        cfg = load_config()
        cfg["enabled"] = False
        app = App(cfg)
        app.root.withdraw()
        app.root.update_idletasks()
        app.rebuild()                      # 渲染 + 两层分层窗口
        app._sync_widgets()                # 预览图 / 说明文字
        lines.append("geometry: %s" % app.root.winfo_geometry())
        lines.append("scrollregion: %s" % app._canvas.cget("scrollregion"))
        lines.append("canvas height: %s" % app._canvas.winfo_height())
        lines.append("preview photo: %s" % bool(app._preview_photo))
        lines.append("status: %s" % app.status_var.get())
        lines.append("footer children: %d" % len(app.root.winfo_children()[1].winfo_children()))
        app.on_close()
        lines.append("uicheck: OK")
    except Exception:
        lines.append("uicheck: FAIL\n" + traceback.format_exc())
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    ok = any("uicheck: OK" in line for line in lines)
    # windowed exe 的控制台代码页不保证 UTF-8，这里只输出 ASCII 摘要；
    # 完整中文结果写入文件。
    print("uicheck:", "OK" if ok else "FAIL", "->", os.path.abspath(out_path))
    return lines


def diagnose(out_path="check_result.txt"):
    """端到端自检：全部图形渲染 + 两层分层窗口 + 淡入淡出 / 微位移。"""
    lines = ["ComfortAnchor %s" % VERSION,
             "python: %s" % sys.version.replace("\n", " "),
             "platform: %s" % platform.platform()]
    try:
        lines.append("pillow: %s" % Image.__version__)
        cfg = dict(C.DEFAULTS)
        cfg.update(PRESETS["standard"])
        for pattern in PATTERNS:
            one = dict(cfg)
            one["pattern"] = pattern.id
            to_bgra_premultiplied(render_overlay(480, 270, one))
        lines.append("render: OK all %d patterns" % len(PATTERNS))
        img = render_overlay(640, 360, cfg)
        lines.append("bgra bytes: %d" % len(to_bgra_premultiplied(img)))
    except Exception:
        lines.append("render: FAIL\n" + traceback.format_exc())

    try:
        mons = list_monitors()
        lines.append("dpi: %d" % (system_dpi() if IS_WINDOWS else 96))
        lines.append("monitors: %s" % repr(mons))
        mon = mons[0]
        w, h = min(mon["width"], 1280), min(mon["height"], 720)
        fw = OverlayWindow(w, h, mon["left"], mon["top"])
        mw = OverlayWindow(w + 2 * MARK_PAD, h + 2 * MARK_PAD,
                           mon["left"] - MARK_PAD, mon["top"] - MARK_PAD)
        fw.set_image(render_frame(w, h, dict(C.DEFAULTS)))
        mw.set_image(render_marks(w + 2 * MARK_PAD, h + 2 * MARK_PAD, dict(C.DEFAULTS)))
        mw.set_fade(120)
        mw.set_fade(255)
        mw.set_offset(4, -3)
        mw.set_offset(0, 0)
        lines.append("layered windows: OK (frame + marks, fade + offset)")
        lines.append("input sampler: %s" % (repr(InputSampler().sample()),))
        fw.destroy()
        mw.destroy()
    except Exception:
        lines.append("layered windows: FAIL\n" + traceback.format_exc())

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return lines


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _arg_out(default):
    if "--out" in sys.argv:
        idx = sys.argv.index("--out")
        if idx + 1 < len(sys.argv):
            return sys.argv[idx + 1]
    return default


def main():
    if "--uicheck" in sys.argv:
        lines = uicheck(_arg_out("ui_check.txt"))
        return 0 if any("uicheck: OK" in line for line in lines) else 1
    if "--check" in sys.argv:
        diagnose(_arg_out("check_result.txt"))
        return 0
    if "--sheet" in sys.argv:
        return make_sheet(_arg_out("patterns.png"))
    if "--selftest" in sys.argv:
        return selftest(_arg_out("preview.png"))
    if "--version" in sys.argv:
        print(VERSION)
        return 0
    if not IS_WINDOWS:
        print("ComfortAnchor 目前仅支持 Windows。")
        return 1
    cfg = load_config()
    try:
        App(cfg).run()
    except Exception:
        with open(log_path(), "w", encoding="utf-8") as fh:
            fh.write(traceback.format_exc())
        try:
            import tkinter.messagebox as mb
            mb.showerror("静锚启动失败", "错误详情已写入:\n" + log_path())
        except Exception:
            pass
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
