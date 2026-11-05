# -*- coding: utf-8 -*-
"""静锚 ComfortAnchor - 配置模型。

职责：默认值、预设、旧版配置迁移、类型校验与本地持久化。
不依赖 Pillow / tkinter / Win32，便于单独测试。
"""
from __future__ import annotations

import json
import os

APP_NAME = "ComfortAnchor"
APP_TITLE = "静锚 ComfortAnchor · 游戏晕动症舒适叠加层"
VERSION = "2.0.0"
SCHEMA = 2

# 单选值域，集中定义避免 UI 与渲染层各写一份
PATTERN_IDS = (
    "none", "dots", "rings", "crosses", "grid", "lines",
    "ticks", "horizon", "dome", "radial", "clouds",
)
MOTION_MODES = ("static", "adaptive", "counter", "follow")
COLOR_IDS = ("neutral", "dark", "light", "amber", "cyan")

MOTION_LABELS = {
    "static": "绝对静止（循证推荐）",
    "adaptive": "明度自适应（Cao 2018 动态参照框）",
    "counter": "反向光流微动（实验性）",
    "follow": "同向跟随微动（无证据，不推荐）",
}

MOTION_NOTES = {
    "static": "屏幕空间固定 = 与真实世界对齐。桌面显示器上这是证据最强的形态，"
              "且不会引入任何额外光流。",
    "adaptive": "参照标记的不透明度随操作强度淡入淡出；静止时几乎不可见，"
                "可显著减少常驻遮挡。Cao 2018 的 dynamic rest frame 指的就是"
                "「不透明度变化」，不是位置移动；该研究只有静态版达到显著减晕。",
    "counter": "标记朝画面光流的反方向做极小幅位移（≤12px），思路来自 Park 2022"
               " 反向光流实验。仅在低对比度下不明显分心；属未经验证的实验功能。",
    "follow": "标记与画面光流同向微移，等于叠加额外光流。Buhler 2018 的同类方案"
              "未取得显著效果（N=18）。仅用于对照自测，不建议日常使用。",
}

MARK_COLORS = {
    "neutral": (128, 128, 128),
    "dark": (24, 24, 28),
    "light": (235, 235, 238),
    "amber": (196, 148, 76),
    "cyan": (92, 176, 190),
}

MARK_COLOR_LABELS = {
    "neutral": "中性灰（亮暗画面通用）",
    "dark": "深色",
    "light": "浅色",
    "amber": "琥珀（低蓝光）",
    "cyan": "青蓝",
}

# 数值型配置的合法区间。渲染层与 UI 共用，防止越界。
LIMITS = {
    "opacity": (0, 40),
    "size": (1, 12),
    "density": (0, 80),
    "vignette": (0, 20),
    "inner_clear": (25, 85),
    "hud_guard": (0, 25),
    "drift_gain": (0, 12),
}

DEFAULTS = {
    "schema": SCHEMA,
    "enabled": True,
    "monitor_index": 0,
    "preset": "minimal",
    "pattern": "none",
    "opacity": 9,
    "size": 2,
    "density": 18,
    "vignette": 0,          # 默认关闭暗角：它是「画面发灰」的主因之一
    "inner_clear": 62,      # 中央完全透明区更大，避开准星与主要战斗信息
    "hud_guard": 10,        # 四角避让区，默认保护小地图 / 技能栏
    "show_border": True,
    "show_ticks": True,
    "show_horizon": False,
    "show_crosshair": False,  # Shi 2021：中央准星无显著减晕优势
    "mark_color": "neutral",
    "motion_mode": "static",
    "drift_gain": 6,
}

# 预设只覆盖「视觉与运动」参数，不触碰 enabled / monitor_index。
# 极简为默认：Baek & Kim 2025 指出密度变化对减晕与临场感均无显著影响，
# 在效果相近时应优先选择遮挡最少的配置。
PRESETS = {
    "minimal": {
        "pattern": "none", "opacity": 8, "size": 2, "density": 15,
        "vignette": 0, "inner_clear": 65, "hud_guard": 12,
        "show_border": True, "show_ticks": True, "motion_mode": "static",
    },
    "gentle": {
        "pattern": "dots", "opacity": 8, "size": 3, "density": 10,
        "vignette": 0, "inner_clear": 60, "hud_guard": 10,
        "show_border": True, "show_ticks": True, "motion_mode": "static",
    },
    "standard": {
        "pattern": "grid", "opacity": 10, "size": 2, "density": 22,
        "vignette": 3, "inner_clear": 55, "hud_guard": 10,
        "show_border": True, "show_ticks": True, "motion_mode": "static",
    },
    "strong": {
        "pattern": "grid", "opacity": 15, "size": 3, "density": 38,
        "vignette": 7, "inner_clear": 45, "hud_guard": 8,
        "show_border": True, "show_ticks": True, "motion_mode": "static",
    },
}

PRESET_LABELS = {
    "minimal": "极简",
    "gentle": "柔和",
    "standard": "标准",
    "strong": "增强",
    "custom": "自定义",
}

HOTKEY_HELP = ("Ctrl+Alt+D 开关 · Ctrl+Alt+S 面板 · Ctrl+Alt+P 切换图形 · F9 紧急关闭")


def clamp(value, low, high):
    return max(low, min(high, value))


def app_folder():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    folder = os.path.join(base, APP_NAME)
    os.makedirs(folder, exist_ok=True)
    return folder


def config_path():
    return os.path.join(app_folder(), "settings.json")


def log_path():
    return os.path.join(app_folder(), "crash.log")


def sanitize(cfg):
    """把任意来源的配置收敛到合法值域，返回新 dict。"""
    out = dict(DEFAULTS)
    for key, default in DEFAULTS.items():
        if key not in cfg:
            continue
        value = cfg[key]
        if isinstance(default, bool):
            if isinstance(value, bool):
                out[key] = value
        elif isinstance(default, int):
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                lo, hi = LIMITS.get(key, (0, 1000))
                out[key] = int(clamp(round(value), lo, hi))
        elif isinstance(default, str):
            if isinstance(value, str):
                allowed = {
                    "pattern": PATTERN_IDS,
                    "motion_mode": MOTION_MODES,
                    "mark_color": COLOR_IDS,
                }.get(key)
                if allowed is None or value in allowed:
                    out[key] = value
    out["schema"] = SCHEMA
    return out


def _migrate_v1(saved):
    """v1 配置尽力映射到 v2；重点是把过密的颗粒降下来。"""
    strength = clamp(float(saved.get("strength", 100)), 20, 160) / 100.0
    border = clamp(float(saved.get("border", 14)), 0, 40)
    grain_density = clamp(float(saved.get("grain_density", 25)), 0, 60)
    mapped = {
        "enabled": bool(saved.get("enabled", True)),
        "monitor_index": int(saved.get("monitor_index", 0)),
        "preset": "gentle" if saved.get("show_grains", True) else "minimal",
        "pattern": "dots" if saved.get("show_grains", True) else "none",
        "opacity": clamp(round(border * strength * 0.65), 3, 20),
        "size": clamp(round(float(saved.get("grain_size", 6)) * 0.5), 2, 6),
        "density": clamp(round(grain_density * 0.5), 0, 35),
        "vignette": clamp(round(float(saved.get("vignette", 12)) * strength * 0.35), 0, 8),
        "inner_clear": clamp(max(60, float(saved.get("inner_clear", 45))), 25, 85),
        "hud_guard": 10,
        "show_border": bool(saved.get("show_border", True)),
        "show_ticks": bool(saved.get("show_ticks", True)),
        "show_horizon": bool(saved.get("show_horizon", False)),
        "show_crosshair": bool(saved.get("show_crosshair", False)),
        "mark_color": saved.get("mark_color", "neutral"),
        "motion_mode": "static",
        "drift_gain": 6,
    }
    return sanitize(mapped)


def load_config():
    try:
        with open(config_path(), "r", encoding="utf-8") as fh:
            saved = json.load(fh)
        if not isinstance(saved, dict):
            return dict(DEFAULTS)
        if saved.get("schema", 1) < SCHEMA:
            return _migrate_v1(saved)
        return sanitize(saved)
    except (OSError, ValueError, TypeError):
        return dict(DEFAULTS)


def save_config(cfg):
    try:
        with open(config_path(), "w", encoding="utf-8") as fh:
            json.dump(sanitize(cfg), fh, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


def apply_preset(cfg, key):
    """就地应用预设，返回被修改的键集合。"""
    if key not in PRESETS:
        return set()
    changed = set(PRESETS[key])
    cfg.update(PRESETS[key])
    cfg["preset"] = key
    return changed
