# -*- coding: utf-8 -*-
"""静锚 ComfortAnchor - 纯 Pillow 渲染层。

职责：把所有参照图形渲染成 RGBA 位图。与 Win32、tkinter、配置持久化完全解耦，
因此可在无 GUI 环境下做自检、生成预览图和图形对照表。

分两层渲染：
  * frame 层：暗角 / 细边框 / 四角刻线 / 地平线 / 准星 —— 绝对静止，永不动。
  * marks 层：用户选择的参照图形 —— 可被覆盖率掩码裁切，可选微动 / 明度自适应。
两层分离保证即使开启实验性微动，与重力对齐的主参照框仍然严格静止。
"""
from __future__ import annotations

import math
import os
import random
from dataclasses import dataclass
from typing import Callable

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from ca_config import MARK_COLORS, clamp

# 微动模式会平移 marks 层，留出画布余量避免边缘露出空白
MARK_PAD = 16
GRAIN_SEED = 20261105  # 固定种子：图形位置恒定，绝不随机闪动


@dataclass(frozen=True)
class RenderSpec:
    w: int
    h: int
    rgb: tuple
    alpha: int
    size: int
    density: int
    line_w: int
    spacing: int
    seed: int


@dataclass(frozen=True)
class PatternSpec:
    id: str
    label: str
    note: str
    painter: Callable  # (layer: Image, draw: ImageDraw, s: RenderSpec) -> None


def _a(percent):
    """不透明度百分比 -> 0..255 alpha。"""
    return int(clamp(round(255.0 * percent / 100.0), 0, 255))


def _spec(w, h, cfg):
    size = clamp(int(cfg.get("size", 2)), 1, 12)
    density = clamp(int(cfg.get("density", 18)), 0, 80)
    rgb = MARK_COLORS.get(cfg.get("mark_color", "neutral"), MARK_COLORS["neutral"])
    return RenderSpec(
        w=w, h=h, rgb=rgb,
        alpha=_a(cfg.get("opacity", 9)),
        size=size,
        density=density,
        line_w=max(1, min(3, size // 2 + 1)),
        spacing=max(size * 5, int(112 - density * 0.85)),
        seed=GRAIN_SEED,
    )


# ---------------------------------------------------------------------------
# 参照图形：每个函数只负责往 layer 上画一种形状，不关心掩码与窗口
# ---------------------------------------------------------------------------

def _p_none(layer, draw, s):
    return


def _points(s):
    """统一的稀疏候选点网格；密度只改间距，不再制造上万个实心圆。"""
    rng = random.Random(s.seed)
    y = s.spacing // 2
    while y < s.h:
        x = s.spacing // 2
        while x < s.w:
            if rng.random() < 0.88:
                jx = x + rng.uniform(-s.spacing * 0.16, s.spacing * 0.16)
                jy = y + rng.uniform(-s.spacing * 0.16, s.spacing * 0.16)
                yield jx, jy
            x += s.spacing
        y += s.spacing


def _p_dots(layer, draw, s):
    r = max(1.0, s.size / 2.0)
    fill = s.rgb + (s.alpha,)
    for x, y in _points(s):
        draw.ellipse([x - r, y - r, x + r, y + r], fill=fill)


def _p_rings(layer, draw, s):
    r = max(3.0, s.size * 1.7)
    outline = s.rgb + (clamp(int(s.alpha * 1.15), 0, 255),)
    for x, y in _points(s):
        draw.ellipse([x - r, y - r, x + r, y + r], outline=outline, width=s.line_w)


def _p_crosses(layer, draw, s):
    arm = max(3, s.size * 2)
    fill = s.rgb + (clamp(int(s.alpha * 1.1), 0, 255),)
    for x, y in _points(s):
        draw.line([(x - arm, y), (x + arm, y)], fill=fill, width=s.line_w)
        draw.line([(x, y - arm), (x, y + arm)], fill=fill, width=s.line_w)


def _p_grid(layer, draw, s):
    fill = s.rgb + (s.alpha,)
    step = max(s.spacing, 24)
    for x in range(step // 2, s.w, step):
        draw.line([(x, 0), (x, s.h)], fill=fill, width=s.line_w)
    for y in range(step // 2, s.h, step):
        draw.line([(0, y), (s.w, y)], fill=fill, width=s.line_w)


def _p_lines(layer, draw, s):
    """Chang 2013：两横两竖白色细线把画面分成九宫格，最省像素的重力参照。"""
    fill = s.rgb + (clamp(int(s.alpha * 1.3), 0, 255),)
    for fx in (1 / 3, 2 / 3):
        x = int(s.w * fx)
        draw.line([(x, 0), (x, s.h)], fill=fill, width=s.line_w)
    for fy in (1 / 3, 2 / 3):
        y = int(s.h * fy)
        draw.line([(0, y), (s.w, y)], fill=fill, width=s.line_w)


def _p_ticks(layer, draw, s):
    """Dot[9] side-tick 风格：四边等距短刻度，全部水平/垂直。"""
    fill = s.rgb + (clamp(int(s.alpha * 1.4), 0, 255),)
    step = max(s.spacing // 2, 28)
    short, long = max(4, s.size * 2), max(8, s.size * 5)
    i = 0
    for x in range(step, s.w, step):
        d = long if i % 4 == 0 else short
        draw.line([(x, 0), (x, d)], fill=fill, width=s.line_w)
        draw.line([(x, s.h - d), (x, s.h)], fill=fill, width=s.line_w)
        i += 1
    i = 0
    for y in range(step, s.h, step):
        d = long if i % 4 == 0 else short
        draw.line([(0, y), (d, y)], fill=fill, width=s.line_w)
        draw.line([(s.w - d, y), (s.w, y)], fill=fill, width=s.line_w)
        i += 1


def _p_horizon(layer, draw, s):
    """Dot[9] 分段地平线：与重力垂直对齐，中央留缺口。"""
    fill = s.rgb + (clamp(int(s.alpha * 1.3), 0, 255),)
    y = s.h // 2
    gap = int(s.w * 0.16)
    seg = max(24, s.spacing)
    for x in range(0, s.w // 2 - gap, seg * 2):
        draw.line([(x, y), (min(x + seg, s.w // 2 - gap), y)], fill=fill, width=s.line_w)
    for x in range(s.w // 2 + gap, s.w, seg * 2):
        draw.line([(x, y), (min(x + seg, s.w), y)], fill=fill, width=s.line_w)


def _p_dome(layer, draw, s):
    """Steady 的 Dome：椭圆穹顶 + 水平地平线，整体严格水平垂直。"""
    fill = s.rgb + (s.alpha,)
    m = int(min(s.w, s.h) * 0.045)
    draw.ellipse([m, m, s.w - m, s.h - m], outline=fill, width=s.line_w)
    y = s.h // 2
    gap = int(s.w * 0.18)
    draw.line([(m, y), (s.w // 2 - gap, y)], fill=fill, width=s.line_w)
    draw.line([(s.w // 2 + gap, y), (s.w - m, y)], fill=fill, width=s.line_w)


def _p_radial(layer, draw, s):
    """边缘径向短刻度：整体对称、不旋转，提供周边方位参照。"""
    fill = s.rgb + (s.alpha,)
    cx, cy = s.w / 2.0, s.h / 2.0
    rx, ry = s.w * 0.47, s.h * 0.47
    count = 56
    for i in range(count):
        ang = 2.0 * math.pi * i / count
        ca, sa = math.cos(ang), math.sin(ang)
        x1, y1 = cx + ca * rx * 0.93, cy + sa * ry * 0.93
        x2, y2 = cx + ca * rx, cy + sa * ry
        draw.line([(x1, y1), (x2, y2)], fill=fill, width=s.line_w)


def _p_clouds(layer, draw, s):
    """Lin 等：由有意义物体构成的自然 IVB 在恶心评分上优于网格；
    这里用极淡的柔边云团做低遮挡近似。"""
    soft = Image.new("L", (s.w, s.h), 0)
    sd = ImageDraw.Draw(soft)
    rng = random.Random(s.seed + 7)
    n = max(8, 18 + s.density // 6)
    for _ in range(n):
        cx = rng.uniform(0, s.w)
        cy = rng.uniform(0, s.h)
        rw = rng.uniform(s.w * 0.05, s.w * 0.13)
        rh = rng.uniform(s.h * 0.04, s.h * 0.10)
        sd.ellipse([cx - rw, cy - rh, cx + rw, cy + rh], fill=38)
    soft = soft.filter(ImageFilter.GaussianBlur(radius=max(10, min(s.w, s.h) // 55)))
    tint = Image.new("RGBA", (s.w, s.h), s.rgb + (0,))
    tint.putalpha(soft)
    layer.alpha_composite(tint)


PATTERNS = (
    PatternSpec("none", "无标记（仅细边框）",
                "零遮挡。仅保留 1px 静止边框与四角刻线，适合先确认是否分心。", _p_none),
    PatternSpec("dots", "稀疏圆点",
                "Cao 2021 颗粒化参照框的桌面近似。注意该论文只测视觉搜索、未测晕动症；"
                "此版密度比 v1 低一个数量级以消除画面发灰。", _p_dots),
    PatternSpec("rings", "空心圆环",
                "同密度下墨迹面积远小于实心点，适合想保留点阵节奏但更在意清晰度的场景。", _p_rings),
    PatternSpec("crosses", "小十字",
                "水平/垂直双向线段，强化重力方向信息（Kim 2026：只有重力对齐的参照有效）。", _p_crosses),
    PatternSpec("grid", "细网格 / 金属网",
                "Cao 2018 的 see-through metal mesh、Chang 2013 的静态网格、Baek 2025 的 mesh RF；"
                "是原始实验里证据最扎实的形状之一。", _p_grid),
    PatternSpec("lines", "两横两竖（九宫格）",
                "Chang 2013, n=22 脑电实验用的极简网格，像素占用最低。", _p_lines),
    PatternSpec("ticks", "四边短刻度",
                "借鉴 Dot[9] 的 side-tick 地平线风格；只在最外圈留下刻度，避开中央。", _p_ticks),
    PatternSpec("horizon", "分段地平线",
                "Dot[9] / Prothero 的 IVB：水平线是最强的「主观竖直」提示，中央断开避免挡准星。", _p_horizon),
    PatternSpec("dome", "椭圆穹顶＋地平线",
                "借鉴 Steady 的 Dome 形状：椭圆轮廓 + 水平线，整体严格不旋转。", _p_dome),
    PatternSpec("radial", "边缘径向刻度",
                "径向排列的短刻度，只在最外圈，提供周边方位而不侵入中央视野。", _p_radial),
    PatternSpec("clouds", "柔和云状自然参照",
                "Lin 等报告「由有意义物体构成的自然 IVB」在恶心评分上优于纯网格；"
                "此处为极淡的柔边近似，属探索性选项。", _p_clouds),
)

PATTERN_BY_ID = {p.id: p for p in PATTERNS}
PATTERN_LABELS = {p.id: p.label for p in PATTERNS}


# ---------------------------------------------------------------------------
# 掩码
# ---------------------------------------------------------------------------

def _vignette_mask(w, h, inner, max_alpha):
    """低分辨率生成软边椭圆暗角，再放大，避免逐像素遍历全屏。"""
    sw, sh = max(64, w // 4), max(64, h // 4)
    data = bytearray(sw * sh)
    cx, cy = sw / 2.0, sh / 2.0
    rx, ry = sw / 2.0, sh / 2.0
    span = max(1e-6, 1.0 - inner)
    for y in range(sh):
        dy = (y - cy) / ry
        dy2 = dy * dy
        row = y * sw
        for x in range(sw):
            dx = (x - cx) / rx
            d = math.sqrt(dx * dx + dy2)
            if d <= inner:
                data[row + x] = 0
            elif d >= 1.0:
                data[row + x] = max_alpha
            else:
                t = (d - inner) / span
                t = t * t * (3.0 - 2.0 * t)
                data[row + x] = int(max_alpha * t)
    return Image.frombytes("L", (sw, sh), bytes(data)).resize((w, h), Image.BILINEAR)


def coverage_mask(w, h, inner_pct, hud_guard_pct):
    """marks 层覆盖率掩码：中央完全透明 + 四角 HUD 避让，边界柔化。

    Baek & Kim 2025：中央 120°×60° 保持 mesh-free，且低 density / low opacity
    在减晕效果相近时显著减少视觉遮挡与临场感损失。
    """
    mask = Image.new("L", (w, h), 255)
    d = ImageDraw.Draw(mask)
    inner = clamp(inner_pct / 100.0, 0.20, 0.88)
    cx, cy = w / 2.0, h / 2.0
    rx, ry = cx * inner, cy * inner
    d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=0)

    guard = clamp(hud_guard_pct, 0, 25)
    if guard > 0:
        g = int(min(w, h) * guard / 100.0)
        # 最外圈留白给 1px 边框 / 四角刻线；HUD 一般从更靠内的位置开始
        e = int(min(w, h) * 0.022)
        if g > e:
            for rect in (
                (e, e, g, g), (w - g, e, w - e, g),
                (e, h - g, g, h - e), (w - g, h - g, w - e, h - e),
            ):
                d.rectangle(rect, fill=0)
    return mask.filter(ImageFilter.GaussianBlur(radius=max(4, min(w, h) // 170)))


# ---------------------------------------------------------------------------
# 两层渲染
# ---------------------------------------------------------------------------

def render_frame(w, h, cfg):
    """绝对静止的参照框层。所有线条水平/垂直，代码中没有任何 rotate。"""
    inner = clamp(cfg.get("inner_clear", 62) / 100.0, 0.20, 0.88)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    vignette = cfg.get("vignette", 0)
    if vignette > 0:
        black = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        black.putalpha(_vignette_mask(w, h, inner, _a(vignette)))
        img = Image.alpha_composite(img, black)

    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    s = _spec(w, h, cfg)
    rgb = s.rgb
    base = s.alpha

    if cfg.get("show_border", True) and base > 0:
        inset = 3
        draw.rectangle([inset, inset, w - inset - 1, h - inset - 1],
                       outline=rgb + (clamp(int(base * 1.35), 0, 255),), width=1)

    if cfg.get("show_ticks", True) and base > 0:
        tick_a = clamp(int(base * 1.7), 0, 255)
        length, m = 20, 4
        for sx, sy, dx, dy in (
            (m, m, 1, 1), (w - m, m, -1, 1),
            (m, h - m, 1, -1), (w - m, h - m, -1, -1),
        ):
            draw.line([(sx, sy), (sx + dx * length, sy)], fill=rgb + (tick_a,), width=1)
            draw.line([(sx, sy), (sx, sy + dy * length)], fill=rgb + (tick_a,), width=1)

    if cfg.get("show_horizon", False) and base > 0:
        line_a = clamp(int(base * 1.1), 0, 255)
        cy, gap = h // 2, int(w * 0.14)
        draw.line([(4, cy), (w // 2 - gap, cy)], fill=rgb + (line_a,), width=1)
        draw.line([(w // 2 + gap, cy), (w - 5, cy)], fill=rgb + (line_a,), width=1)

    if cfg.get("show_crosshair", False) and base > 0:
        dot_a = clamp(int(base * 1.4), 0, 255)
        cx, cy, r = w // 2, h // 2, 4
        draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                     outline=rgb + (dot_a,), width=1)

    return Image.alpha_composite(img, layer)


def render_marks(canvas_w, canvas_h, cfg):
    """可选微动 / 明度自适应的图形层；中央与四角 HUD 区被掩码抹去。"""
    s = _spec(canvas_w, canvas_h, cfg)
    layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    pattern = PATTERN_BY_ID.get(cfg.get("pattern", "none"), PATTERNS[0])
    pattern.painter(layer, draw, s)

    mask = coverage_mask(canvas_w, canvas_h,
                         cfg.get("inner_clear", 62), cfg.get("hud_guard", 10))
    layer.putalpha(ImageChops.multiply(layer.getchannel("A"), mask))
    return layer


def render_overlay(w, h, cfg):
    """静态合成图，仅用于预览 / 自检 / 图形对照表。"""
    frame = render_frame(w, h, cfg)
    cw, ch = w + 2 * MARK_PAD, h + 2 * MARK_PAD
    marks = render_marks(cw, ch, cfg).crop((MARK_PAD, MARK_PAD, MARK_PAD + w, MARK_PAD + h))
    return Image.alpha_composite(frame, marks)


def to_bgra_premultiplied(img):
    """UpdateLayeredWindow 要求 32bpp BGRA 且 alpha 预乘。"""
    alpha = img.getchannel("A")
    r = ImageChops.multiply(img.getchannel("R"), alpha)
    g = ImageChops.multiply(img.getchannel("G"), alpha)
    b = ImageChops.multiply(img.getchannel("B"), alpha)
    return Image.merge("RGBA", (b, g, r, alpha)).tobytes()


# ---------------------------------------------------------------------------
# 预览素材
# ---------------------------------------------------------------------------

def mock_game_frame(w, h):
    """模拟一张偏暗、带透视与 HUD 的 3D 游戏画面，用来观察遮挡程度。"""
    bg = Image.new("RGBA", (w, h), (26, 32, 44, 255))
    d = ImageDraw.Draw(bg)
    horizon = h // 2
    for i in range(0, w, max(32, w // 20)):
        shade = 26 + int(18 * (i / w))
        d.line([(i, h), (w // 2 + (i - w // 2) * 0.22, horizon)],
               fill=(shade, shade + 8, shade + 18, 255), width=1)
    for j in range(1, 9):
        y = horizon + int((j / 9) ** 1.7 * (h - horizon))
        d.line([(0, y), (w, y)], fill=(38 + j * 2, 46 + j * 2, 60 + j * 3, 255), width=1)
    d.polygon([(w // 2, horizon - 110), (w // 2 + w * 0.17, horizon + 80),
               (w // 2 - w * 0.17, horizon + 80)],
              outline=(74, 88, 108, 255), width=2)
    # 角落 HUD：用于肉眼检查避让区是否生效
    hud = (92, 104, 120, 255)
    d.rectangle([int(w * 0.035), int(h * 0.76), int(w * 0.16), int(h * 0.955)],
                outline=hud, width=2)
    d.rectangle([int(w * 0.84), int(h * 0.87), int(w * 0.965), int(h * 0.955)],
                outline=hud, width=2)
    return bg


def _load_font(size):
    """加载系统中文字体，仅用于生成图形对照表；不随项目分发字体文件。

    从 WINDIR 推导字体目录，避免硬编码盘符（系统可能装在非 C 盘）。
    找不到时退回 Pillow 内置字体，功能不受影响。
    """
    windir = os.environ.get("WINDIR") or os.environ.get("SystemRoot") or "C:/Windows"
    fonts = os.path.join(windir, "Fonts")
    for name in ("msyh.ttc", "msyhbd.ttc", "simhei.ttf"):
        try:
            return ImageFont.truetype(os.path.join(fonts, name), size)
        except OSError:
            continue
    return ImageFont.load_default()


def pattern_sheet(cfg, cols=3, cell=(440, 248)):
    """生成所有参照图形的对照表，便于挑选形状。

    对照表刻意把不透明度/密度调高到「看得清」的水平，仅用于比较形状；
    日常使用的默认配置比这里淡得多。
    """
    cw, ch = cell
    rows = math.ceil(len(PATTERNS) / cols)
    sheet = Image.new("RGB", (cols * cw, rows * (ch + 52)), (18, 20, 26))
    d = ImageDraw.Draw(sheet)
    font = _load_font(17)
    small = _load_font(12)
    for i, pattern in enumerate(PATTERNS):
        col, row = i % cols, i // cols
        x0, y0 = col * cw, row * (ch + 52)
        one = dict(cfg)
        one.update({
            "pattern": pattern.id,
            "opacity": 18, "size": 3, "density": 42,
            "vignette": 0, "inner_clear": 50, "hud_guard": 8,
            "show_border": True, "show_ticks": True,
        })
        layer = render_overlay(cw, ch, one)
        composed = Image.alpha_composite(mock_game_frame(cw, ch), layer).convert("RGB")
        sheet.paste(composed, (x0, y0))
        d.text((x0 + 10, y0 + ch + 6), "%s  [%s]" % (pattern.label, pattern.id),
               fill=(235, 236, 240), font=font)
        d.text((x0 + 10, y0 + ch + 30), pattern.note[:26],
               fill=(150, 156, 168), font=small)
        d.rectangle([x0, y0, x0 + cw - 1, y0 + ch - 1], outline=(58, 62, 72), width=1)
    return sheet
