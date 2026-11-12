"""
x11_transparency.py - "Transparent" theme support on Linux (X11 / XWayland).

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.

On Windows the Transparent theme relies on Tk's `-transparentcolor` window attribute,
which Tk does not provide on X11. Here the same effect is obtained with the X Shape
extension: the main window is clipped to the parts that are *not* the key colour,
so only text, icons and controls stay visible (and clickable), as on Windows.

Pixels outside a window's shape are never repainted, so while the window is clipped
the visible state of every widget is polled, and only the area of a widget that
changed is briefly un-clipped, repainted and clipped again.  Polled are the usual
options (text, image, colours, state...), variables, the contents of entry, text,
list and tree widgets, canvas items and geometry.  An image whose pixels are changed
in place (e.g. PhotoImage.put()) without any widget option changing is not noticed
until the pointer next enters and leaves the window.

The shape is built on a coarse grid (BLOCK_PX): compositors re-process the whole
shape on every change, and a per-pixel shape of the main window (thousands of
rectangles) stalls e.g. KWin for ~100ms each time, versus ~10ms with 3px blocks.
The price is a thin dark outline around text, which also helps readability.
"""
from __future__ import annotations

import ctypes
import os
import sys
import tkinter as tk
from ctypes import POINTER, Structure, byref, c_int, c_short, c_uint, c_ulong, c_ushort, c_void_p

from EDMCLogging import get_main_logger

logger = get_main_logger()

KEY_COLOUR = 'grey4'  # Same key colour as the Windows implementation
BLOCK_PX = 3  # Shape granularity, see module docstring
POLL_MS = 300  # How often widget state is checked while clipped
REPAINT_AGAIN_MS = 150  # See _clip
LEAVE_MS = 100  # Delay before clipping after the pointer leaves, so quick re-entries don't flicker

# Walks a widget tree (not into other toplevels) and returns, per widget, its path, root-relative geometry,
# mapped state and a string of everything that affects its look.  Options a widget lacks are skipped.
_SNAPSHOT_TCL = r"""
namespace eval ::edmc {}
proc ::edmc::x11_transparency_snapshot {root} {
    set out {}
    set rx [winfo rootx $root]
    set ry [winfo rooty $root]
    set top [winfo toplevel $root]
    set todo [list $root]
    while {[llength $todo]} {
        set w [lindex $todo end]
        set todo [lrange $todo 0 end-1]
        foreach c [winfo children $w] {
            if {[winfo toplevel $c] eq $top} { lappend todo $c }
        }
        set look {}
        foreach o {-text -image -foreground -background -state -font -relief -bitmap -value} {
            if {![catch {$w cget $o} v]} { lappend look $v }
        }
        foreach o {-textvariable -variable} {
            if {![catch {$w cget $o} v] && $v ne ""} {
                catch { lappend look [uplevel #0 [list set $v]] }
            }
        }
        catch { lappend look [$w state] }  ;# ttk widgets: selected, disabled, ...
        switch -- [winfo class $w] {
            Entry - TEntry - TCombobox - Spinbox - TSpinbox { lappend look [$w get] }
            Text { lappend look [$w get 1.0 end] }
            Listbox { lappend look [$w get 0 end] [$w curselection] }
            Treeview {
                foreach item [$w children {}] { lappend look $item [$w item $item] }
            }
            Canvas {
                foreach i [$w find all] { lappend look $i [$w coords $i] [$w itemconfigure $i] }
            }
        }
        lappend out $w [expr {[winfo rootx $w] - $rx}] [expr {[winfo rooty $w] - $ry}] \
            [winfo width $w] [winfo height $w] [winfo ismapped $w] $look
    }
    return $out
}
"""

# Xlib / Shape constants
_ZPIXMAP = 2
_ALL_PLANES = c_ulong(-1).value
_SHAPE_BOUNDING = 0
_SHAPE_SET, _SHAPE_UNION, _SHAPE_SUBTRACT = 0, 1, 3
_UNSORTED = 0
_LSB_FIRST = 0

Rect = tuple[int, int, int, int]


class _XRectangle(Structure):
    _fields_ = [('x', c_short), ('y', c_short), ('width', c_ushort), ('height', c_ushort)]


class _XImage(Structure):
    # Only the leading, stable part of the struct is needed
    _fields_ = [
        ('width', c_int), ('height', c_int), ('xoffset', c_int), ('format', c_int),
        ('data', c_void_p), ('byte_order', c_int), ('bitmap_unit', c_int), ('bitmap_bit_order', c_int),
        ('bitmap_pad', c_int), ('depth', c_int), ('bytes_per_line', c_int), ('bits_per_pixel', c_int),
        ('red_mask', c_ulong), ('green_mask', c_ulong), ('blue_mask', c_ulong),
    ]


def opaque_rects(  # noqa: CCR001
    pixels: memoryview, width: int, height: int, key: int, block: int = BLOCK_PX
) -> list[Rect]:
    """
    Return rectangles covering every `block`-sized cell holding a pixel that isn't `key`.

    :param pixels: 32-bit pixels, row-major, `width` per row (only the low 24 bits are compared).
    :param width: Image width in pixels.
    :param height: Image height in pixels.
    :param key: The transparent colour as 0xRRGGBB.
    :param block: Grid size in pixels.
    :return: (x, y, width, height) rectangles, merged horizontally and vertically.
    """
    block_rows: list[set[int]] = []
    for by in range(0, height, block):
        cells: set[int] = set()
        for y in range(by, min(by + block, height)):
            row = pixels[y * width:(y + 1) * width]
            x = 0
            while x < width:
                if (row[x] & 0xFFFFFF) != key:
                    cells.add(x // block)
                    x = (x // block + 1) * block  # rest of this cell can't change the result
                else:
                    x += 1
        block_rows.append(cells)

    # Turn each grid row into spans of consecutive cells, then merge identical spans vertically
    rects: list[Rect] = []
    open_spans: dict[tuple[int, int], int] = {}
    for gy, cells in enumerate(block_rows + [set()]):
        spans = set()
        start = None
        for cx in sorted(cells):
            if start is None:
                start = end = cx
            elif cx == end + 1:
                end = cx
            else:
                spans.add((start, end + 1))
                start = end = cx
        if start is not None:
            spans.add((start, end + 1))

        for span in [s for s in open_spans if s not in spans]:
            gy0 = open_spans.pop(span)
            rects.append((span[0] * block, gy0 * block, (span[1] - span[0]) * block, (gy - gy0) * block))
        for span in spans:
            open_spans.setdefault(span, gy)

    return rects


class X11Transparency:
    """Emulates Tk's Windows-only `-transparentcolor` for one Tk root window."""

    def __init__(self) -> None:
        self.root: tk.Tk | None = None
        self.enabled = False
        self.clipped = False
        self._key = 0
        self._dpy: c_void_p | None = None
        self._x11: ctypes.CDLL | None = None
        self._xext: ctypes.CDLL | None = None
        self._snapshot: dict[str, tuple] = {}
        self._poll_job: str | None = None
        self._leave_job: str | None = None
        self._available: bool | None = None
        self._tcl_ready = False

    # Public API ----------------------------------------------------------------------------------------------

    def enable(self, root: tk.Tk) -> None:
        """Switch to transparent mode.  The window must be mapped."""
        if not self._load():
            return
        self.root = root
        r, g, b = (c >> 8 for c in root.winfo_rgb(KEY_COLOUR))
        self._key = (r << 16) | (g << 8) | b
        self.enabled = True
        self._clip_soon()

    def disable(self) -> None:
        """Leave transparent mode."""
        self._cancel(self._leave_job)
        self._leave_job = None
        self._unclip()
        self.enabled = False

    def on_enter(self, event: tk.Event | None) -> None:
        """Pointer entered the window: show it whole, as on Windows."""
        if not self.enabled or self._is_focus(event):
            return
        self._cancel(self._leave_job)
        self._leave_job = None
        self._unclip()

    def on_leave(self, event: tk.Event | None) -> None:
        """Pointer left the window: go transparent again."""
        if not self.enabled or self._is_focus(event) or self.root is None:
            return
        # Moving onto a child widget also sends a Leave, immediately followed by an Enter that cancels this.
        # (The crossing coordinates can't tell the two apart: XWayland reports the last position inside.)
        self._clip_soon()

    # Event filtering ---------------------------------------------------------------------------------------

    @staticmethod
    def _is_focus(event: tk.Event | None) -> bool:
        # EDMC binds FocusIn/Out to the same handlers.  Following focus would keep the window opaque after
        # start-up or a click until the pointer had entered and left it, so only pointer crossings count here.
        return event is not None and event.type in (tk.EventType.FocusIn, tk.EventType.FocusOut)

    # Clipping --------------------------------------------------------------------------------------------

    def _clip_soon(self) -> None:
        assert self.root is not None
        self._cancel(self._leave_job)
        self._leave_job = self.root.after(LEAVE_MS, self._clip)

    def _clip(self) -> None:
        """Clip the whole window.  It must be un-clipped, i.e. fully painted, at this point."""
        self._leave_job = None
        if not self.enabled or self.clipped or self.root is None or not self.root.winfo_viewable():
            return
        try:
            self.root.update_idletasks()
            window = self._wrapper()
            width, height = self._size(window)
            rects = self._read_rects(window, 0, 0, width, height)
            if rects is None:
                return
            self._shape(window, _SHAPE_SET, 0, 0, rects)
            self._force_compositor_repaint(window)
            # Parts Tk repainted just before (e.g. the menu bar swap on leave) can reach the compositor after the
            # first nudge and be left stale, so nudge once more after it has rendered a few frames.
            self.root.after(REPAINT_AGAIN_MS, self._repaint_again)
            self.clipped = True
            self._snapshot = self._take_snapshot()
            self._poll_job = self.root.after(POLL_MS, self._poll)
        except Exception:
            logger.exception('Could not clip the window for the transparent theme')

    def _repaint_again(self) -> None:
        if self.clipped:
            self._force_compositor_repaint(self._wrapper())

    def _unclip(self) -> None:
        if not self.clipped:
            return
        self.clipped = False
        self._cancel(self._poll_job)
        self._poll_job = None
        try:
            assert self._xext is not None
            self._xext.XShapeCombineMask(self._dpy, self._wrapper(), _SHAPE_BOUNDING, 0, 0, 0, _SHAPE_SET)
            self._x11.XFlush(self._dpy)  # type: ignore[union-attr]
        except Exception:
            logger.exception('Could not un-clip the window for the transparent theme')

    def _poll(self) -> None:
        """While clipped, find widgets whose look changed and re-clip only their area."""
        self._poll_job = None
        if not self.clipped or self.root is None:
            return
        try:
            snapshot = self._take_snapshot()
            changed = [path for path, state in snapshot.items() if self._snapshot.get(path) != state]
            changed += [path for path in self._snapshot if path not in snapshot]  # destroyed: old area
            old, self._snapshot = self._snapshot, snapshot
            if changed:
                self._refresh([old.get(p) for p in changed] + [snapshot.get(p) for p in changed])
        except Exception:
            logger.exception('Transparent theme refresh failed')
        if self.clipped:
            self._poll_job = self.root.after(POLL_MS, self._poll)

    def _refresh(self, states: list[tuple | None]) -> None:
        """Repaint and re-clip the area covered by these widget states (old and new geometry)."""
        assert self.root is not None
        boxes = [s[0] for s in states if s is not None and s[0][4]]  # mapped geometries only
        if not boxes:
            return
        window = self._wrapper()
        width, height = self._size(window)
        ox, oy = self._root_offset(window)
        x0 = min(b[0] for b in boxes) + ox
        y0 = min(b[1] for b in boxes) + oy
        x1 = max(b[0] + b[2] for b in boxes) + ox
        y1 = max(b[1] + b[3] for b in boxes) + oy
        # Align to the grid so the new part matches the rest of the shape
        x0, y0 = max(0, x0 // BLOCK_PX * BLOCK_PX), max(0, y0 // BLOCK_PX * BLOCK_PX)
        x1 = min(width, -(-x1 // BLOCK_PX) * BLOCK_PX)
        y1 = min(height, -(-y1 // BLOCK_PX) * BLOCK_PX)
        if x1 <= x0 or y1 <= y0:
            return

        area = [(x0, y0, x1 - x0, y1 - y0)]
        self._shape(window, _SHAPE_UNION, 0, 0, area)
        self._repaint(x0 - ox, y0 - oy, x1 - x0, y1 - y0)
        rects = self._read_rects(window, x0, y0, x1 - x0, y1 - y0)
        self._shape(window, _SHAPE_SUBTRACT, 0, 0, area)
        if rects:
            self._shape(window, _SHAPE_UNION, x0, y0, rects)
        self._force_compositor_repaint(window)

    def _repaint(self, x: int, y: int, width: int, height: int) -> None:
        """Have Tk repaint every widget intersecting this root-relative area, right now."""
        assert self.root is not None
        for path, ((wx, wy, ww, wh, mapped), _look) in self._snapshot.items():
            if mapped and wx < x + width and x < wx + ww and wy < y + height and y < wy + wh:
                # A synthetic Expose makes Tk schedule a full redisplay of the widget, which update_idletasks
                # then performs.  Waiting for the server's Expose instead races with reading the pixels back.
                # (Plain Tcl call: plugins may create widgets that have no tkinter object for nametowidget().)
                self.root.tk.call('event', 'generate', path, '<Expose>', '-when', 'now')
        self.root.update_idletasks()

    # Widget state polling --------------------------------------------------------------------------------

    def _take_snapshot(self) -> dict[str, tuple]:
        """Return {widget path: ((x, y, width, height, mapped), look)} for the root and its descendants."""
        assert self.root is not None
        if not self._tcl_ready:
            self.root.tk.eval(_SNAPSHOT_TCL)
            self._tcl_ready = True
        # One Tcl call for the whole tree: hundreds of Python -> Tcl round trips took ~50ms per poll
        flat = self.root.tk.splitlist(self.root.tk.call('::edmc::x11_transparency_snapshot', str(self.root)))
        snapshot: dict[str, tuple] = {}
        for i in range(0, len(flat), 7):
            x, y, w, h, mapped = (int(v) for v in flat[i + 1:i + 6])
            snapshot[str(flat[i])] = ((x, y, w, h, bool(mapped)), flat[i + 6])
        return snapshot

    # X11 helpers -----------------------------------------------------------------------------------------

    def _load(self) -> bool:
        if self._available is not None:
            return self._available
        self._available = False
        if sys.platform != 'linux':
            return False
        try:
            x11 = ctypes.CDLL('libX11.so.6')
            xext = ctypes.CDLL('libXext.so.6')
            x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
            x11.XOpenDisplay.restype = c_void_p
            x11.XFlush.argtypes = [c_void_p]
            x11.XSync.argtypes = [c_void_p, c_int]
            x11.XQueryTree.argtypes = [c_void_p, c_ulong, POINTER(c_ulong), POINTER(c_ulong),
                                       POINTER(c_void_p), POINTER(c_uint)]
            x11.XFree.argtypes = [c_void_p]
            x11.XGetGeometry.argtypes = [c_void_p, c_ulong, POINTER(c_ulong), POINTER(c_int), POINTER(c_int),
                                         POINTER(c_uint), POINTER(c_uint), POINTER(c_uint), POINTER(c_uint)]
            x11.XTranslateCoordinates.argtypes = [c_void_p, c_ulong, c_ulong, c_int, c_int,
                                                  POINTER(c_int), POINTER(c_int), POINTER(c_ulong)]
            x11.XMoveWindow.argtypes = [c_void_p, c_ulong, c_int, c_int]
            x11.XGetImage.argtypes = [c_void_p, c_ulong, c_int, c_int, c_uint, c_uint, c_ulong, c_int]
            x11.XGetImage.restype = POINTER(_XImage)
            x11.XDestroyImage.argtypes = [POINTER(_XImage)]
            xext.XShapeQueryExtension.argtypes = [c_void_p, POINTER(c_int), POINTER(c_int)]
            xext.XShapeCombineMask.argtypes = [c_void_p, c_ulong, c_int, c_int, c_int, c_ulong, c_int]
            xext.XShapeCombineRectangles.argtypes = [c_void_p, c_ulong, c_int, c_int, c_int,
                                                     POINTER(_XRectangle), c_int, c_int, c_int]
            dpy = x11.XOpenDisplay(None)
            if not dpy:
                raise OSError('cannot open X display')
            if not xext.XShapeQueryExtension(dpy, byref(c_int()), byref(c_int())):
                raise OSError('X server lacks the Shape extension')
        except Exception as e:
            logger.warning(f'Transparent theme is unavailable on this system: {e!r}')
            return False
        self._x11, self._xext, self._dpy = x11, xext, dpy
        self._available = True
        return True

    def _wrapper(self) -> int:
        """Return the window the window manager manages: the parent of Tk's root window."""
        assert self.root is not None and self._x11 is not None
        root_ret, parent, children, count = c_ulong(), c_ulong(), c_void_p(), c_uint()
        self._x11.XQueryTree(self._dpy, self.root.winfo_id(), byref(root_ret), byref(parent),
                             byref(children), byref(count))
        if children:
            self._x11.XFree(children)
        return parent.value

    def _size(self, window: int) -> tuple[int, int]:
        assert self._x11 is not None
        root_ret, x, y = c_ulong(), c_int(), c_int()
        width, height, border, depth = c_uint(), c_uint(), c_uint(), c_uint()
        self._x11.XGetGeometry(self._dpy, window, byref(root_ret), byref(x), byref(y),
                               byref(width), byref(height), byref(border), byref(depth))
        return width.value, height.value

    def _root_offset(self, window: int) -> tuple[int, int]:
        """Position of Tk's root window inside the wrapper (e.g. below a native menu bar)."""
        assert self.root is not None and self._x11 is not None
        x, y, child = c_int(), c_int(), c_ulong()
        self._x11.XTranslateCoordinates(self._dpy, self.root.winfo_id(), window, 0, 0,
                                        byref(x), byref(y), byref(child))
        return x.value, y.value

    def _read_rects(self, window: int, x: int, y: int, width: int, height: int) -> list[Rect] | None:
        """Read back an area of the window and return its non-key rectangles, relative to the area."""
        assert self._x11 is not None
        self._x11.XSync(self._dpy, 0)
        image_p = self._x11.XGetImage(self._dpy, window, x, y, width, height, _ALL_PLANES, _ZPIXMAP)
        if not image_p:
            return None
        try:
            image = image_p.contents
            if image.bits_per_pixel != 32 or image.byte_order != (_LSB_FIRST if sys.byteorder == 'little' else 1) \
                    or (image.red_mask, image.green_mask, image.blue_mask) != (0xFF0000, 0xFF00, 0xFF):
                logger.warning('Transparent theme: unsupported X visual, disabling')
                self.enabled = False
                return None
            data = ctypes.string_at(image.data, image.bytes_per_line * image.height)
            stride = image.bytes_per_line // 4
            pixels = memoryview(data).cast('I')
            if stride != width:  # drop row padding
                pixels = memoryview(b''.join(pixels[r * stride:r * stride + width].tobytes()
                                             for r in range(height))).cast('I')
            return opaque_rects(pixels, width, height, self._key)
        finally:
            self._x11.XDestroyImage(image_p)

    def _shape(self, window: int, op: int, x: int, y: int, rects: list[Rect]) -> None:
        assert self._xext is not None and self._x11 is not None
        array = (_XRectangle * len(rects))(*(_XRectangle(*r) for r in rects))
        self._xext.XShapeCombineRectangles(self._dpy, window, _SHAPE_BOUNDING, x, y, array, len(rects),
                                           op, _UNSORTED)
        self._x11.XFlush(self._dpy)

    def _force_compositor_repaint(self, window: int) -> None:
        """
        Make the compositor repaint what is behind the parts just removed from the shape.

        KWin (seen on Plasma 6 / XWayland) only repaints the new, smaller shape, so the removed parts keep showing
        the old window content until something else redraws that screen area.  A geometry change makes it repaint
        the whole window area, so the window is moved by one pixel and straight back (not visible).
        """
        assert self._x11 is not None
        if not os.getenv('WAYLAND_DISPLAY'):
            return  # Only seen under XWayland; with reparenting X11 window managers a move could shift the window
        root_ret, x, y = c_ulong(), c_int(), c_int()
        width, height, border, depth = c_uint(), c_uint(), c_uint(), c_uint()
        self._x11.XGetGeometry(self._dpy, window, byref(root_ret), byref(x), byref(y),
                               byref(width), byref(height), byref(border), byref(depth))
        child = c_ulong()
        self._x11.XTranslateCoordinates(self._dpy, window, root_ret.value, 0, 0, byref(x), byref(y), byref(child))
        self._x11.XMoveWindow(self._dpy, window, x.value + 1, y.value)
        self._x11.XSync(self._dpy, 0)  # two separate moves, so the window manager can't merge them into a no-op
        self._x11.XMoveWindow(self._dpy, window, x.value, y.value)
        self._x11.XFlush(self._dpy)

    def _cancel(self, job: str | None) -> None:
        if job is not None and self.root is not None:
            self.root.after_cancel(job)
