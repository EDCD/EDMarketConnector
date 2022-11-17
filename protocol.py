"""protocol handler for cAPI authorisation."""
# spell-checker: words ntdll GURL alloc wfile instantiatable pyright
import os
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from typing import TYPE_CHECKING, Optional, Type

from config import config
from constants import appname, protocolhandler_redirect
from EDMCLogging import get_main_logger

if TYPE_CHECKING:
    import tkinter

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
        self.lastpayload: Optional[str] = None

    def start(self, master: 'tkinter.Tk') -> None:
        """Start Protocol Handler."""
        self.master = master

    def close(self) -> None:
        """Stop / Close Protocol Handler."""
        pass

    def event(self, url: str) -> None:
        """Generate an auth event."""
        self.lastpayload = url

        logger.trace_if('frontier-auth', f'Payload: {self.lastpayload}')
        if not config.shutting_down:
            logger.debug('event_generate("<<CompanionAuthEvent>>")')
            self.master.event_generate('<<CompanionAuthEvent>>', when="tail")


if sys.platform == 'darwin' and getattr(sys, 'frozen', False):  # noqa: C901 # its guarding ALL macos stuff.
    import struct

    import objc  # type: ignore
    from AppKit import NSAppleEventManager, NSObject  # type: ignore

    kInternetEventClass = kAEGetURL = struct.unpack('>l', b'GURL')[0]  # noqa: N816 # API names
    keyDirectObject = struct.unpack('>l', b'----')[0]  # noqa: N816 # API names

    class DarwinProtocolHandler(GenericProtocolHandler):
        """
        MacOS protocol handler implementation.

        Uses macOS event stuff.
        """

        POLL = 100  # ms

        def start(self, master: 'tkinter.Tk') -> None:
            """Start Protocol Handler."""
            GenericProtocolHandler.start(self, master)
            self.lasturl: Optional[str] = None
            self.eventhandler = EventHandler.alloc().init()

        def poll(self) -> None:
            """Poll event until URL is updated."""
            # No way of signalling to Tkinter from within the callback handler block that doesn't cause Python to crash,
            # so poll. TODO: Resolved?
            if self.lasturl and self.lasturl.startswith(self.redirect):
                self.event(self.lasturl)
                self.lasturl = None

    class EventHandler(NSObject):
        """Handle NSAppleEventManager IPC stuff."""

        def init(self) -> None:
            """
            Init method for handler.

            (I'd assume this is related to the subclassing of NSObject for why its not __init__)
            """
            self = objc.super(EventHandler, self).init()
            NSAppleEventManager.sharedAppleEventManager().setEventHandler_andSelector_forEventClass_andEventID_(
                self,
                'handleEvent:withReplyEvent:',
                kInternetEventClass,
                kAEGetURL
            )
            return self

        def handleEvent_withReplyEvent_(self, event, replyEvent) -> None:  # noqa: N802 N803 # Required to override
            """Actual event handling from NSAppleEventManager."""
            protocolhandler.lasturl = urllib.parse.unquote(  # noqa: F821: type: ignore # It's going to be a DPH in
                # this code
                event.paramDescriptorForKeyword_(keyDirectObject).stringValue()
            ).strip()

            protocolhandler.master.after(DarwinProtocolHandler.POLL, protocolhandler.poll)  # noqa: F821 # type: ignore


elif (config.auth_force_edmc_protocol
      or (
          sys.platform == 'win32'
          and getattr(sys, 'frozen', False)
          and not is_wine
          and not config.auth_force_localserver
      )):
    # spell-checker: words HBRUSH HICON WPARAM wstring WNDCLASS HMENU HGLOBAL
    from ctypes import windll  # type: ignore
    from ctypes import POINTER, WINFUNCTYPE, Structure, byref, c_long, c_void_p, create_unicode_buffer, wstring_at
    from ctypes.wintypes import (
        ATOM, BOOL, DWORD, HBRUSH, HGLOBAL, HICON, HINSTANCE, HMENU, HWND, INT, LPARAM, LPCWSTR, LPVOID, LPWSTR, MSG,
        UINT, WPARAM
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

    GetMessageW = windll.user32.GetMessageW
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
            self.thread: Optional[threading.Thread] = None

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
            while GetMessageW(byref(msg), None, 0, 0) != 0:
                logger.trace_if('frontier-auth.windows', f'DDE message of type: {msg.message}')
                if msg.message == WM_DDE_EXECUTE:
                    # GlobalLock does some sort of "please dont move this?"
                    # https://docs.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-globallock
                    args = wstring_at(GlobalLock(msg.lParam)).strip()
                    GlobalUnlock(msg.lParam)  # Unlocks the GlobalLock-ed object

                    if args.lower().startswith('open("') and args.endswith('")'):
                        logger.trace_if('frontier-auth.windows', f'args are: {args}')
                        url = urllib.parse.unquote(args[6:-2]).strip()
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

            self.thread: Optional[threading.Thread] = None

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
            url = urllib.parse.unquote(self.path)
            if url.startswith('/auth'):
                logger.debug('Request starts with /auth, sending to protocolhandler.event()')
                protocolhandler.event(url)  # noqa: F821
                self.send_response(200)
                return True
            else:
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
                self.wfile.write('<html><head><title>Authentication successful</title></head>'.encode('utf-8'))
                self.wfile.write('<body><p>Authentication successful</p></body>'.encode('utf-8'))
            else:
                self.end_headers()

        def log_request(self, code: int | str = '-', size: int | str = '-') -> None:
            """Override to prevent logging."""
            pass


def get_handler_impl() -> Type[GenericProtocolHandler]:
    """
    Get the appropriate GenericProtocolHandler for the current system and config.

    :return: An instantiatable GenericProtocolHandler
    """
    if sys.platform == 'darwin' and getattr(sys, 'frozen', False):
        return DarwinProtocolHandler  # pyright: reportUnboundVariable=false

    elif (
        (sys.platform == 'win32' and config.auth_force_edmc_protocol)
        or (getattr(sys, 'frozen', False) and not is_wine and not config.auth_force_localserver)
    ):
        return WindowsProtocolHandler

    else:
        return LinuxProtocolHandler


# *late init* singleton
protocolhandler: GenericProtocolHandler
