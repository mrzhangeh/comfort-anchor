# -*- coding: utf-8 -*-
"""静锚 ComfortAnchor - Win32 透明分层窗口与被动输入采样。

设计约束：
  * 不注入游戏、不 hook 内存/输入、不截屏、不联网、不安装全局钩子。
  * 分层窗口使用 WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE，
    通过 UpdateLayeredWindow 推送 32bpp 预乘 BGRA 位图。
  * DIBSection 与内存 DC 常驻缓存：明度自适应 / 微动只改 BLENDFUNCTION.SourceConstantAlpha
    或目标位置，不重新渲染、不重新分配位图，也不逐帧重绘。
  * 输入采样只用 GetCursorPos / GetAsyncKeyState 只读轮询。
"""
from __future__ import annotations

import ctypes
import math
import platform
from ctypes import wintypes

from ca_render import to_bgra_premultiplied

IS_WINDOWS = platform.system() == "Windows"

if IS_WINDOWS:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    # 必须在创建任何窗口前声明 DPI 感知，否则显示器尺寸会被系统虚拟化。
    try:
        user32.SetProcessDPIAware.argtypes = []
        user32.SetProcessDPIAware.restype = wintypes.BOOL
        user32.SetProcessDPIAware()
    except Exception:
        pass

    WS_POPUP = 0x80000000
    WS_EX_LAYERED = 0x00080000
    WS_EX_TRANSPARENT = 0x00000020
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_NOACTIVATE = 0x08000000
    ULW_ALPHA = 0x00000002
    AC_SRC_OVER = 0x00
    AC_SRC_ALPHA = 0x01
    BI_RGB = 0
    DIB_RGB_COLORS = 0
    SW_SHOW = 5
    SW_HIDE = 0
    WM_CLOSE = 0x0010
    MONITORINFOF_PRIMARY = 0x00000001
    LOGPIXELSX = 88
    HWND_TOPMOST = ctypes.c_void_p(-1)
    SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE, SWP_SHOWWINDOW = 0x0001, 0x0002, 0x0010, 0x0040

    class POINT(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

    class SIZE(ctypes.Structure):
        _fields_ = [("cx", wintypes.LONG), ("cy", wintypes.LONG)]

    class RECT(ctypes.Structure):
        _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                    ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

    class BLENDFUNCTION(ctypes.Structure):
        _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                    ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                    ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                    ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                    ("biClrImportant", wintypes.DWORD)]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 1)]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", RECT),
                    ("rcWork", RECT), ("dwFlags", wintypes.DWORD)]

    class WNDCLASS(ctypes.Structure):
        _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", ctypes.c_void_p),
                    ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                    ("hInstance", ctypes.c_void_p), ("hIcon", ctypes.c_void_p),
                    ("hCursor", ctypes.c_void_p), ("hbrBackground", ctypes.c_void_p),
                    ("lpszMenuName", ctypes.c_wchar_p), ("lpszClassName", ctypes.c_wchar_p)]

    WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_void_p,
                                 wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p)
    MONITORENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, ctypes.c_void_p,
                                         ctypes.c_void_p, ctypes.POINTER(RECT),
                                         ctypes.c_void_p)

    user32.DefWindowProcW.argtypes = [ctypes.c_void_p, wintypes.UINT,
                                      ctypes.c_void_p, ctypes.c_void_p]
    user32.DefWindowProcW.restype = ctypes.c_ssize_t
    user32.CreateWindowExW.argtypes = [wintypes.DWORD, ctypes.c_wchar_p, ctypes.c_wchar_p,
                                       wintypes.DWORD, ctypes.c_int, ctypes.c_int,
                                       ctypes.c_int, ctypes.c_int, ctypes.c_void_p,
                                       ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    user32.CreateWindowExW.restype = ctypes.c_void_p
    user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASS)]
    user32.RegisterClassW.restype = wintypes.ATOM
    user32.GetDC.argtypes = [ctypes.c_void_p]
    user32.GetDC.restype = ctypes.c_void_p
    user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    user32.DestroyWindow.argtypes = [ctypes.c_void_p]
    user32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user32.UpdateLayeredWindow.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(POINT), ctypes.POINTER(SIZE),
        ctypes.c_void_p, ctypes.POINTER(POINT), wintypes.DWORD,
        ctypes.POINTER(BLENDFUNCTION), wintypes.DWORD]
    user32.UpdateLayeredWindow.restype = wintypes.BOOL
    user32.EnumDisplayMonitors.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                           MONITORENUMPROC, ctypes.c_void_p]
    user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(MONITORINFO)]
    user32.GetMonitorInfoW.restype = wintypes.BOOL
    user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
    user32.GetAsyncKeyState.restype = ctypes.c_short
    user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
    user32.GetCursorPos.restype = wintypes.BOOL
    user32.GetSystemMetrics.argtypes = [ctypes.c_int]
    user32.GetSystemMetrics.restype = ctypes.c_int
    gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
    gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
    gdi32.CreateDIBSection.argtypes = [ctypes.c_void_p, ctypes.POINTER(BITMAPINFO),
                                       wintypes.UINT, ctypes.POINTER(ctypes.c_void_p),
                                       ctypes.c_void_p, wintypes.DWORD]
    gdi32.CreateDIBSection.restype = ctypes.c_void_p
    gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    gdi32.SelectObject.restype = ctypes.c_void_p
    gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
    gdi32.DeleteDC.argtypes = [ctypes.c_void_p]
    gdi32.GetDeviceCaps.argtypes = [ctypes.c_void_p, ctypes.c_int]
    gdi32.GetDeviceCaps.restype = ctypes.c_int
    kernel32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
    kernel32.GetModuleHandleW.restype = ctypes.c_void_p

    @WNDPROC
    def _wnd_proc(hwnd, msg, wparam, lparam):
        if msg == WM_CLOSE:
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    _WNDPROC_KEEPALIVE = _wnd_proc
    _CLASS_REGISTERED = False

    def _ensure_class():
        global _CLASS_REGISTERED
        if _CLASS_REGISTERED:
            return
        wc = WNDCLASS()
        wc.lpfnWndProc = ctypes.cast(_WNDPROC_KEEPALIVE, ctypes.c_void_p)
        wc.hInstance = kernel32.GetModuleHandleW(None)
        wc.lpszClassName = "ComfortAnchorOverlayV2"
        if not user32.RegisterClassW(ctypes.byref(wc)):
            raise ctypes.WinError(ctypes.get_last_error())
        _CLASS_REGISTERED = True

    def system_dpi():
        hdc = user32.GetDC(None)
        try:
            return gdi32.GetDeviceCaps(hdc, LOGPIXELSX) or 96
        finally:
            user32.ReleaseDC(None, hdc)

    def list_monitors():
        result = []

        @MONITORENUMPROC
        def cb(hmon, hdc, lprc, lparam):
            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(MONITORINFO)
            primary = False
            if user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
                primary = bool(info.dwFlags & MONITORINFOF_PRIMARY)
                rc = info.rcMonitor
            else:
                rc = lprc.contents
            result.append({
                "left": rc.left, "top": rc.top,
                "width": rc.right - rc.left, "height": rc.bottom - rc.top,
                "primary": primary,
            })
            return True

        user32.EnumDisplayMonitors(None, None, cb, None)
        if not result:
            result.append({"left": 0, "top": 0,
                           "width": user32.GetSystemMetrics(0),
                           "height": user32.GetSystemMetrics(1),
                           "primary": True})
        result.sort(key=lambda m: (not m["primary"], m["left"], m["top"]))
        return result

    class OverlayWindow:
        """一个鼠标穿透、置顶、可独立淡入淡出与微位移的分层窗口。"""

        def __init__(self, width, height, base_x, base_y):
            _ensure_class()
            self.base_x, self.base_y = int(base_x), int(base_y)
            self.offset_x = self.offset_y = 0
            self.fade = 255
            self.hwnd = user32.CreateWindowExW(
                WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
                "ComfortAnchorOverlayV2", "ComfortAnchor", WS_POPUP,
                self.base_x, self.base_y, int(width), int(height),
                None, None, kernel32.GetModuleHandleW(None), None,
            )
            if not self.hwnd:
                raise ctypes.WinError(ctypes.get_last_error())
            user32.SetWindowPos(self.hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                                SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE)
            user32.ShowWindow(self.hwnd, SW_HIDE)  # 等 set_enabled 决定显隐
            self._hdc_mem = gdi32.CreateCompatibleDC(None)
            if not self._hdc_mem:
                raise ctypes.WinError(ctypes.get_last_error())
            self._hbitmap = None
            self._old_bitmap = None
            self._bits = None
            self._size = (0, 0)
            self._visible = False

        def _alloc_dib(self, w, h):
            if self._hbitmap:
                gdi32.SelectObject(self._hdc_mem, self._old_bitmap)
                gdi32.DeleteObject(self._hbitmap)
                self._hbitmap = None
            bmi = BITMAPINFO()
            hdr = bmi.bmiHeader
            hdr.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            hdr.biWidth = w
            hdr.biHeight = -h  # top-down
            hdr.biPlanes = 1
            hdr.biBitCount = 32
            hdr.biCompression = BI_RGB
            bits = ctypes.c_void_p()
            hbitmap = gdi32.CreateDIBSection(
                self._hdc_mem, ctypes.byref(bmi), DIB_RGB_COLORS,
                ctypes.byref(bits), None, 0)
            if not hbitmap or not bits.value:
                raise ctypes.WinError(ctypes.get_last_error())
            self._old_bitmap = gdi32.SelectObject(self._hdc_mem, hbitmap)
            self._hbitmap = hbitmap
            self._bits = bits.value
            self._size = (w, h)

        def set_image(self, img):
            w, h = img.size
            if (w, h) != self._size or not self._hbitmap:
                self._alloc_dib(w, h)
            data = to_bgra_premultiplied(img)
            ctypes.memmove(self._bits, data, len(data))
            self._update()

        def _update(self):
            if not self._hbitmap:
                return
            hdc_screen = user32.GetDC(None)
            try:
                size = SIZE(self._size[0], self._size[1])
                src = POINT(0, 0)
                dst = POINT(self.base_x + self.offset_x, self.base_y + self.offset_y)
                blend = BLENDFUNCTION(AC_SRC_OVER, 0, self.fade, AC_SRC_ALPHA)
                ok = user32.UpdateLayeredWindow(
                    self.hwnd, hdc_screen, ctypes.byref(dst), ctypes.byref(size),
                    self._hdc_mem, ctypes.byref(src), 0, ctypes.byref(blend), ULW_ALPHA)
                err = ctypes.get_last_error()
            finally:
                user32.ReleaseDC(None, hdc_screen)
            if not ok:
                raise ctypes.WinError(err)

        def set_fade(self, value):
            value = int(max(0, min(255, value)))
            if value != self.fade:
                self.fade = value
                self._update()

        def set_offset(self, dx, dy):
            dx, dy = int(dx), int(dy)
            if (dx, dy) != (self.offset_x, self.offset_y):
                self.offset_x, self.offset_y = dx, dy
                self._update()

        def show(self):
            user32.ShowWindow(self.hwnd, SW_SHOW)
            user32.SetWindowPos(self.hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                                SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE | SWP_SHOWWINDOW)
            self._visible = True

        def hide(self):
            user32.ShowWindow(self.hwnd, SW_HIDE)
            self._visible = False

        def destroy(self):
            if self._hbitmap:
                gdi32.SelectObject(self._hdc_mem, self._old_bitmap)
                gdi32.DeleteObject(self._hbitmap)
                self._hbitmap = None
            if self._hdc_mem:
                gdi32.DeleteDC(self._hdc_mem)
                self._hdc_mem = None
            if self.hwnd:
                user32.DestroyWindow(self.hwnd)
                self.hwnd = None

    class InputSampler:
        """只读采样鼠标位移与按键状态，用作「运动强度」与方向的粗略代理。

        局限：采用 raw input 且锁定光标的 FPS 游戏里 GetCursorPos 可能不变化，
        此时退化为 WASD / 方向键估计。不会为取数据而 hook 或注入输入。
        """

        VK = {"W": 0x57, "A": 0x41, "S": 0x53, "D": 0x44,
              "UP": 0x26, "DOWN": 0x28, "LEFT": 0x25, "RIGHT": 0x27,
              "SPACE": 0x20, "LBUTTON": 0x01, "RBUTTON": 0x02}

        def __init__(self):
            self._last = None

        def _down(self, vk):
            return bool(user32.GetAsyncKeyState(vk) & 0x8000)

        def sample(self):
            pt = POINT()
            has_cursor = bool(user32.GetCursorPos(ctypes.byref(pt)))
            dx = dy = 0
            if has_cursor:
                if self._last is not None:
                    dx = pt.x - self._last[0]
                    dy = pt.y - self._last[1]
                self._last = (pt.x, pt.y)
            speed = min(1.0, math.hypot(dx, dy) / 18.0)

            right = self._down(self.VK["D"]) or self._down(self.VK["RIGHT"])
            left = self._down(self.VK["A"]) or self._down(self.VK["LEFT"])
            down = self._down(self.VK["S"]) or self._down(self.VK["DOWN"])
            up = self._down(self.VK["W"]) or self._down(self.VK["UP"])
            kx, ky = (1 if right else 0) - (1 if left else 0), (1 if down else 0) - (1 if up else 0)
            key_busy = any((right, left, down, up,
                            self._down(self.VK["SPACE"]),
                            self._down(self.VK["LBUTTON"]),
                            self._down(self.VK["RBUTTON"])))
            activity = max(speed, 0.55 if key_busy else 0.0)

            if speed > 0.02:
                nx, ny = dx / max(1e-6, math.hypot(dx, dy)), dy / max(1e-6, math.hypot(dx, dy))
            elif kx or ky:
                norm = math.hypot(kx, ky)
                nx, ny = kx / norm, ky / norm
            else:
                nx = ny = 0.0
            return activity, nx, ny

else:  # pragma: no cover - 仅用于非 Windows 下的自检
    class OverlayWindow:
        def __init__(self, width, height, base_x, base_y):
            self.base_x, self.base_y = base_x, base_y
            self.offset_x = self.offset_y = 0
            self.fade = 255
            self.hwnd = None
            self._visible = False

        def set_image(self, img):
            pass

        def set_fade(self, value):
            self.fade = int(max(0, min(255, value)))

        def set_offset(self, dx, dy):
            self.offset_x, self.offset_y = int(dx), int(dy)

        def show(self):
            self._visible = True

        def hide(self):
            self._visible = False

        def destroy(self):
            pass

    class InputSampler:
        def sample(self):
            return 0.0, 0.0, 0.0

    def list_monitors():
        return [{"left": 0, "top": 0, "width": 1920, "height": 1080, "primary": True}]

    def system_dpi():
        return 96
