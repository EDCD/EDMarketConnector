# flake8: noqa
# mypy: ignore-errors
"""Test myNotebook with Pytest."""

import pytest
import tkinter as tk
from tkinter import ttk
from unittest.mock import MagicMock, patch
import myNotebook


@pytest.fixture(scope="session")
def root():
    """Create a single root window for all tests to avoid 'TclError: can't invoke "grid" command'."""
    root = tk.Tk()
    root.withdraw()  # Hide the window
    yield root
    root.destroy()


class TestWidgetHacks:
    def test_notebook_colors_windows(self, root):
        """Verify that on Windows, specific styles are configured with PAGEBG."""
        with patch("sys.platform", "win32"):
            nb = myNotebook.Notebook(root)
            style = ttk.Style()
            # PAGEBG is 'SystemWindow' on win32
            assert style.lookup("nb.TFrame", "background") == "SystemWindow"
            nb.destroy()

    def test_label_colors_windows(self, root):
        """Verify Label uses system window colors on Windows."""
        with patch("sys.platform", "win32"):
            # Ensure we are using the module's constants
            label = myNotebook.Label(root, text="Test")

            # Cast to str() to handle Tcl/Tk color objects
            assert str(label["background"]) == "SystemWindow"
            assert str(label["foreground"]) == "SystemWindowText"

            label.destroy()


class TestEntryMenu:
    def test_select_all(self, root):
        """Verify select_all logic correctly selects text range."""
        entry = myNotebook.EntryMenu(root)
        entry.insert(0, "Hello World")
        entry.select_all()

        assert entry.selection_present() is True
        entry.destroy()

    @patch("tkinter.messagebox.showwarning")
    @patch("PIL.ImageGrab.grabclipboard")
    def test_paste_image_refusal(self, mock_grab, mock_warn, root):
        """Verify that trying to paste an image triggers a warning and aborts."""
        mock_grab.return_value = MagicMock(spec=["save"])  # Simulate an Image object
        entry = myNotebook.EntryMenu(root)

        entry.paste()

        mock_warn.assert_called_once()
        assert entry.get() == ""  # Should not have pasted anything
        entry.destroy()


class TestScrollableNotebook:
    def test_add_synchronization(self, root):
        """Ensure adding a tab adds to both the tab bar and the content notebook."""
        snb = myNotebook.ScrollableNotebook(root)
        frame = ttk.Frame(snb)

        snb.add(frame, text="Tab 1")

        assert len(snb.notebookTab.tabs()) == 1
        assert len(snb.notebookContent.tabs()) == 1
        # Content tab should have empty text as per the code
        assert snb.notebookContent.tab(0, "text") == ""
        snb.destroy()

    def test_forget_synchronization(self, root):
        """Verify forget removes the child and the corresponding tabs."""
        snb = myNotebook.ScrollableNotebook(root)
        frame = ttk.Frame(snb)
        snb.add(frame, text="Tab 1")

        tab_id = snb.tabs()[0]
        snb.forget(tab_id)

        assert len(snb.tabs()) == 0
        assert len(snb.notebookContent.tabs()) == 0
        snb.destroy()

    def test_slide_logic_bounds(self, root):
        """Verify left slide doesn't move if already at 0."""
        snb = myNotebook.ScrollableNotebook(root)
        snb.xLocation = 0

        # _left_slide returns True if it moved, False otherwise
        moved = snb._left_slide(None)

        assert moved is False
        assert snb.xLocation == 0
        snb.destroy()
