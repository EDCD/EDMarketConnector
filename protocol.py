"""
protocol.py - Protocol Handler for cAPI Auth.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.
"""
from __future__ import annotations

import os
import sys
import threading
from urllib import parse
from typing import TYPE_CHECKING, Type

from config import config
from constants import appname, protocolhandler_redirect
from EDMCLogging import get_main_logger

if TYPE_CHECKING:
    import wx

logger = get_main_logger()

is_wine = False

if sys.platform == 'win32':
    from ctypes import windll  # type: ignore

    try:
        if windll.ntdll.wine_get_version:
            is_wine = True
    except Exception:
        pass


class GenericProtocolHandler:
    """Base Protocol Handler."""

    def __init__(self) -> None:
        self.redirect = protocolhandler_redirect  # Base redirection URL
        self.master: 'tkinter.Tk' = None  # type: ignore
        self.lastpayload: str | None = None

    def start(self, master: 'tkinter.Tk') -> None:
        """Start Protocol Handler."""
        self.master = master

    def close(self) -> None:
        """Stop / Close Protocol Handler."""

    def event(self, url: str) -> None:
        """Generate an auth event."""
        self.lastpayload = url

        logger.trace_if('frontier-auth', f'Payload: {self.lastpayload}')
        if not config.shutting_down:
            logger.debug('event_generate("<<CompanionAuthEvent>>")')
            self.master.event_generate('<<CompanionAuthEvent>>', when="tail")


if (config.auth_force_edmc_protocol  # noqa: C901
        or (
                sys.platform == 'win32'
                and getattr(sys, 'frozen', False)
                and not is_wine
                and not config.auth_force_localserver
        )):
    # This could be false if you use auth_force_edmc_protocol, but then you get to keep the pieces
    assert sys.platform == 'win32'
    # spell-checker: words HBRUSH HICON WPARAM wstring WNDCLASS HMENU HGLOBAL
    from ctypes import (  # type: ignore
        windll, POINTER, WINFUNCTYPE, Structure, byref, c_long, c_void_p, create_unicode_buffer, wstring_at
    )
    from ctypes.wintypes import (
        ATOM, BOOL, DWORD, HBRUSH, HGLOBAL, HICON, HINSTANCE, HMENU, HWND, INT, LPARAM, LPCWSTR, LPMSG, LPVOID, LPWSTR,
        MSG, UINT, WPARAM
    )

    class WNDCLASS(Structure):
        """
        A WNDCLASS structure.

        Ref: <https://docs.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-wndclassa>
             <https://docs.microsoft.com/en-us/windows/win32/intl/registering-window-classes>
        """

        _fields_ = [
            ('style', UINT),
            ('lpfnWndProc', WINFUNCTYPE(c_long, HWND, UINT, WPARAM, LPARAM)),
            ('cbClsExtra', INT),
            ('cbWndExtra', INT),
            ('hInstance', HINSTANCE),
            ('hIcon', HICON),
            ('hCursor', c_void_p),
            ('hbrBackground', HBRUSH),
            ('lpszMenuName', LPCWSTR),
            ('lpszClassName', LPCWSTR)
        ]

    CW_USEDEFAULT = 0x80000000

    CreateWindowExW = windll.user32.CreateWindowExW
    CreateWindowExW.argtypes = [DWORD, LPCWSTR, LPCWSTR, DWORD, INT, INT, INT, INT, HWND, HMENU, HINSTANCE, LPVOID]
    CreateWindowExW.restype = HWND
    RegisterClassW = windll.user32.RegisterClassW
    RegisterClassW.argtypes = [POINTER(WNDCLASS)]
    # DefWindowProcW
    # Ref: <https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-defwindowprocw>
    # LRESULT DefWindowProcW([in] HWND   hWnd,[in] UINT   Msg,[in] WPARAM wParam,[in] LPARAM lParam);
    # As per example at <https://docs.python.org/3/library/ctypes.html#ctypes.WINFUNCTYPE>

    prototype = WINFUNCTYPE(c_long, HWND, UINT, WPARAM, LPARAM)
    paramflags = (1, "hWnd"), (1, "Msg"), (1, "wParam"), (1, "lParam")
    DefWindowProcW = prototype(("DefWindowProcW", windll.user32), paramflags)

    GetParent = windll.user32.GetParent
    SetForegroundWindow = windll.user32.SetForegroundWindow

    # <https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getmessagew>
    # NB: Despite 'BOOL' return type, it *can* be >0, 0 or -1, so is actually
    #     c_long
    prototype = WINFUNCTYPE(c_long, LPMSG, HWND, UINT, UINT)
    paramflags = (1, "lpMsg"), (1, "hWnd"), (1, "wMsgFilterMin"), (1, "wMsgFilterMax")
    GetMessageW = prototype(("GetMessageW", windll.user32), paramflags)

    TranslateMessage = windll.user32.TranslateMessage
    DispatchMessageW = windll.user32.DispatchMessageW
    PostThreadMessageW = windll.user32.PostThreadMessageW
    SendMessageW = windll.user32.SendMessageW
    SendMessageW.argtypes = [HWND, UINT, WPARAM, LPARAM]
    PostMessageW = windll.user32.PostMessageW
    PostMessageW.argtypes = [HWND, UINT, WPARAM, LPARAM]

    WM_QUIT = 0x0012
    # https://docs.microsoft.com/en-us/windows/win32/dataxchg/wm-dde-initiate
    WM_DDE_INITIATE = 0x03E0
    WM_DDE_TERMINATE = 0x03E1
    WM_DDE_ACK = 0x03E4
    WM_DDE_EXECUTE = 0x03E8

    PackDDElParam = windll.user32.PackDDElParam
    PackDDElParam.argtypes = [UINT, LPARAM, LPARAM]

    GlobalAddAtomW = windll.kernel32.GlobalAddAtomW
    GlobalAddAtomW.argtypes = [LPWSTR]
    GlobalAddAtomW.restype = ATOM
    GlobalGetAtomNameW = windll.kernel32.GlobalGetAtomNameW
    GlobalGetAtomNameW.argtypes = [ATOM, LPWSTR, INT]
    GlobalGetAtomNameW.restype = UINT
    GlobalLock = windll.kernel32.GlobalLock
    GlobalLock.argtypes = [HGLOBAL]
    GlobalLock.restype = LPVOID
    GlobalUnlock = windll.kernel32.GlobalUnlock
    GlobalUnlock.argtypes = [HGLOBAL]
    GlobalUnlock.restype = BOOL

    # Windows Message handler stuff (IPC)
    # https://docs.microsoft.com/en-us/previous-versions/windows/desktop/legacy/ms633573(v=vs.85)
    @WINFUNCTYPE(c_long, HWND, UINT, WPARAM, LPARAM)
    def WndProc(hwnd: HWND, message: UINT, wParam: WPARAM, lParam: LPARAM) -> c_long:  # noqa: N803 N802
        """
        Deal with DDE requests.

        :param hwnd: Window handle
        :param message: The message being sent
        :param wParam: Additional Message Information (depends on message type)
        :param lParam: Also additional message information
        :return: ???
        """
        if message != WM_DDE_INITIATE:
            # Not a DDE init message, bail and tell windows to do the default
            # https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-defwindowproca?redirectedfrom=MSDN
            return DefWindowProcW(hwnd, message, wParam, lParam)

        service = create_unicode_buffer(256)
        topic = create_unicode_buffer(256)
        # Note that lParam is 32 bits, and broken into two 16 bit words. This will break on 64bit as the math is
        # wrong
        # if nonzero, the target application for which a conversation is requested
        lparam_low = lParam & 0xFFFF  # type: ignore
        # if nonzero, the topic of said conversation
        lparam_high = lParam >> 16  # type: ignore

        # if either of the words are nonzero, they contain
        # atoms https://docs.microsoft.com/en-us/windows/win32/dataxchg/about-atom-tables
        # which we can read out as shown below, and then compare.

        target_is_valid = lparam_low == 0 or (
                GlobalGetAtomNameW(lparam_low, service, 256) and service.value == appname
        )

        topic_is_valid = lparam_high == 0 or (
                GlobalGetAtomNameW(lparam_high, topic, 256) and topic.value.lower() == 'system'
        )

        if target_is_valid and topic_is_valid:
            # if everything is happy, send an acknowledgement of the DDE request
            SendMessageW(
                wParam, WM_DDE_ACK, hwnd, PackDDElParam(WM_DDE_ACK, GlobalAddAtomW(appname), GlobalAddAtomW('System'))
            )

            # It works as a constructor as per <https://docs.python.org/3/library/ctypes.html#fundamental-data-types>
            return c_long(0)

        return c_long(1)  # This is an utter guess -Ath

    class WindowsProtocolHandler(GenericProtocolHandler):
        """
        Windows implementation of GenericProtocolHandler.

        This works by using windows Dynamic Data Exchange to pass messages between processes
        https://en.wikipedia.org/wiki/Dynamic_Data_Exchange
        """

        def __init__(self) -> None:
            super().__init__()
            self.thread: threading.Thread | None = None

        def start(self, master: 'tkinter.Tk') -> None:
            """Start the DDE thread."""
            super().start(master)
            self.thread = threading.Thread(target=self.worker, name='DDE worker')
            self.thread.daemon = True
            self.thread.start()

        def close(self) -> None:
            """Stop the DDE thread."""
            thread = self.thread
            if thread:
                self.thread = None
                PostThreadMessageW(thread.ident, WM_QUIT, 0, 0)
                thread.join()  # Wait for it to quit

        def worker(self) -> None:
            """Start a DDE server."""
            wndclass = WNDCLASS()
            wndclass.style = 0
            wndclass.lpfnWndProc = WndProc
            wndclass.cbClsExtra = 0
            wndclass.cbWndExtra = 0
            wndclass.hInstance = windll.kernel32.GetModuleHandleW(0)
            wndclass.hIcon = None
            wndclass.hCursor = None
            wndclass.hbrBackground = None
            wndclass.lpszMenuName = None
            wndclass.lpszClassName = 'DDEServer'

            if not RegisterClassW(byref(wndclass)):
                print('Failed to register Dynamic Data Exchange for cAPI')
                return

            # https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-createwindowexw
            hwnd = CreateWindowExW(
                0,                       # dwExStyle
                wndclass.lpszClassName,  # lpClassName
                "DDE Server",            # lpWindowName
                0,                       # dwStyle
                CW_USEDEFAULT, CW_USEDEFAULT, CW_USEDEFAULT, CW_USEDEFAULT,  # X, Y, nWidth, nHeight
                self.master.winfo_id(),  # hWndParent # Don't use HWND_MESSAGE since the window won't get DDE broadcasts
                None,                    # hMenu
                wndclass.hInstance,      # hInstance
                None                     # lpParam
            )

            msg = MSG()
            # Calls GetMessageW: https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getmessagew
            # Something is off with the return from this, meaning you'll see:
            # Exception ignored on converting result of ctypes callback function: <function WndProc
            #    at 0x000001F5B8738FE0>
            # Traceback (most recent call last):
            #   File "C:\Users\Athan\Documents\Devel\EDMarketConnector\protocol.py", line 323, in worker
            #     while int(GetMessageW(byref(msg), None, 0, 0)) != 0:
            #               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
            # TypeError: 'c_long' object cannot be interpreted as an integer
            #
            # But it does actually work.  Either getting a non-0 value and
            # entering the loop, or getting 0 and exiting it.
            while GetMessageW(byref(msg), None, 0, 0) != 0:
                logger.trace_if('frontier-auth.windows', f'DDE message of type: {msg.message}')
                if msg.message == WM_DDE_EXECUTE:
                    # GlobalLock does some sort of "please dont move this?"
                    # https://docs.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-globallock
                    args = wstring_at(GlobalLock(msg.lParam)).strip()
                    GlobalUnlock(msg.lParam)  # Unlocks the GlobalLock-ed object

                    if args.lower().startswith('open("') and args.endswith('")'):
                        logger.trace_if('frontier-auth.windows', f'args are: {args}')
                        url = parse.unquote(args[6:-2]).strip()
                        if url.startswith(self.redirect):
                            logger.debug(f'Message starts with {self.redirect}')
                            self.event(url)

                        SetForegroundWindow(GetParent(self.master.winfo_id()))  # raise app window
                        # Send back a WM_DDE_ACK. this is _required_ with WM_DDE_EXECUTE
                        PostMessageW(msg.wParam, WM_DDE_ACK, hwnd, PackDDElParam(WM_DDE_ACK, 0x80, msg.lParam))

                    else:
                        # Send back a WM_DDE_ACK. this is _required_ with WM_DDE_EXECUTE
                        PostMessageW(msg.wParam, WM_DDE_ACK, hwnd, PackDDElParam(WM_DDE_ACK, 0, msg.lParam))

                elif msg.message == WM_DDE_TERMINATE:
                    PostMessageW(msg.wParam, WM_DDE_TERMINATE, hwnd, 0)

                else:
                    TranslateMessage(byref(msg))  # "Translates virtual key messages into character messages" ???
                    DispatchMessageW(byref(msg))


else:  # Linux / Run from source

    from http.server import BaseHTTPRequestHandler, HTTPServer

    class LinuxProtocolHandler(GenericProtocolHandler):
        """
        Implementation of GenericProtocolHandler.

        This implementation uses a localhost HTTP server
        """

        def __init__(self) -> None:
            super().__init__()
            self.httpd = HTTPServer(('localhost', 0), HTTPRequestHandler)
            self.redirect = f'http://localhost:{self.httpd.server_port}/auth'
            if not os.getenv("EDMC_NO_UI"):
                logger.info(f'Web server listening on {self.redirect}')

            self.thread: threading.Thread | None = None

        def start(self, master: 'tkinter.Tk') -> None:
            """Start the HTTP server thread."""
            GenericProtocolHandler.start(self, master)
            self.thread = threading.Thread(target=self.worker, name='OAuth worker')
            self.thread.daemon = True
            self.thread.start()

        def close(self) -> None:
            """Shutdown the HTTP server thread."""
            thread = self.thread
            if thread:
                logger.debug('Thread')
                self.thread = None

                if self.httpd:
                    logger.info('Shutting down httpd')
                    self.httpd.shutdown()

                logger.info('Joining thread')
                thread.join()  # Wait for it to quit

            else:
                logger.debug('No thread')

            logger.debug('Done.')

        def worker(self) -> None:
            """HTTP Worker."""
            # TODO: This should probably be more ephemeral, and only handle one request, as its all we're expecting
            self.httpd.serve_forever()

    class HTTPRequestHandler(BaseHTTPRequestHandler):
        """Simple HTTP server to handle IPC from protocol handler."""

        def parse(self) -> bool:
            """Parse a request."""
            logger.trace_if('frontier-auth.http', f'Got message on path: {self.path}')
            url = parse.unquote(self.path)
            if url.startswith('/auth'):
                logger.debug('Request starts with /auth, sending to protocolhandler.event()')
                protocolhandler.event(url)
                self.send_response(200)
                return True
            self.send_response(404)  # Not found
            return False

        def do_HEAD(self) -> None:  # noqa: N802 # Required to override
            """Handle HEAD Request."""
            self.parse()
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802 # Required to override
            """Handle GET Request."""
            if self.parse():
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write(self._generate_auth_response().encode('utf-8'))
            else:
                self.send_response(404)
                self.end_headers()

        def log_request(self, code: int | str = '-', size: int | str = '-') -> None:
            """Override to prevent logging."""

        def _generate_auth_response(self) -> str:
            """
            Generate the authentication response HTML.

            :return: The HTML content of the authentication response.
            """
            return (
                '<html>'
                '<head>'
                '<title>Authentication successful - Elite: Dangerous</title>'
                '<style>'
                'body { background-color: #000; color: #fff; font-family: "Helvetica Neue", Arial, sans-serif; }'
                'h1 { text-align: center; margin-top: 100px; }'
                'p { text-align: center; }'
                '</style>'
                '</head>'
                '<body>'
                '<h1>Authentication successful</h1>'
                '<p>Thank you for authenticating.</p>'
                '<p>Please close this browser tab now.</p>'
                '</body>'
                '</html>'
            )


def get_handler_impl() -> Type[GenericProtocolHandler]:
    """
    Get the appropriate GenericProtocolHandler for the current system and config.

    :return: An instantiatable GenericProtocolHandler
    """
    if (
            (sys.platform == 'win32' and config.auth_force_edmc_protocol)
            or (getattr(sys, 'frozen', False) and not is_wine and not config.auth_force_localserver)
    ):
        return WindowsProtocolHandler

    return LinuxProtocolHandler


# *late init* singleton
protocolhandler: GenericProtocolHandler
