"""Tests for the shape computation of the Linux Transparent theme."""
from __future__ import annotations

from array import array

import pytest

from x11_transparency import opaque_rects

K = 0x0A0A0A  # key colour
T = 0xFF8000  # text (opaque) colour


def pixels(rows: list[list[int]]) -> memoryview:
    """Pack rows of 0xRRGGBB values as 32-bit pixels with a non-zero padding byte, like XGetImage."""
    return memoryview(array('I', [0xFF000000 | p for row in rows for p in row]))


@pytest.mark.parametrize(
    ('rows', 'block', 'expected'),
    [
        pytest.param([[K, K], [K, K]], 1, [], id='all key'),
        pytest.param([[K, T, T, K], [T, K, K, K]], 1, [(1, 0, 2, 1), (0, 1, 1, 1)], id='per pixel'),
        pytest.param([[T, K, T], [T, K, T]], 1, [(0, 0, 1, 2), (2, 0, 1, 2)], id='vertical merge'),
        pytest.param([[K, K, K, K, T, K]] * 2 + [[K] * 6], 3, [(3, 0, 3, 3)], id='one block'),
        pytest.param([[T, K, K, K, K, K, K]], 3, [(0, 0, 3, 3)], id='partial last row'),
        pytest.param([[K, K, T, T, K, K, K]], 3, [(0, 0, 6, 3)], id='spans two blocks'),
    ],
)
def test_opaque_rects(rows: list[list[int]], block: int, expected: list[tuple[int, int, int, int]]) -> None:
    """Rectangles cover exactly the blocks holding non-key pixels, ignoring the padding byte."""
    width, height = len(rows[0]), len(rows)
    assert sorted(opaque_rects(pixels(rows), width, height, K, block)) == sorted(expected)


def test_opaque_rects_stays_on_grid() -> None:
    """Rectangles are on the block grid even when the image size is not a multiple of it."""
    rects = opaque_rects(pixels([[K] * 4 + [T]]), 5, 1, K, 3)
    assert rects == [(3, 0, 3, 3)]


def test_snapshot_detects_widget_changes() -> None:
    """The Tcl snapshot notices content changes in every covered widget type."""
    import tkinter as tk
    from tkinter import ttk

    from x11_transparency import X11Transparency

    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip('no display')
    root.withdraw()
    try:
        flag = tk.IntVar(master=root, value=1)
        text, listbox, tree = tk.Text(root), tk.Listbox(root), ttk.Treeview(root)
        progress, entry, canvas = ttk.Progressbar(root, value=10), tk.Entry(root), tk.Canvas(root)
        check, label = tk.Checkbutton(root, variable=flag), tk.Label(root, text='unchanged')
        rect = canvas.create_rectangle(0, 0, 5, 5, fill='red')
        row = tree.insert('', 'end', text='row')
        for widget in (text, listbox, tree, progress, entry, canvas, check, label):
            widget.pack()
        root.update_idletasks()

        transparency = X11Transparency()
        transparency.root = root
        before = transparency._take_snapshot()
        text.insert('end', 'hello')
        listbox.insert('end', 'item')
        tree.item(row, text='row 2')
        progress['value'] = 50
        entry.insert(0, 'typed')
        canvas.itemconfigure(rect, outline='blue')
        flag.set(0)
        after = transparency._take_snapshot()

        changed = {path for path in after if before.get(path) != after[path]}
        assert changed == {str(w) for w in (text, listbox, tree, progress, entry, canvas, check)}
    finally:
        root.destroy()
