# edmc: protocol handler for cAPI authorisation


import sys
import threading
from typing import Optional
import urllib.error
import urllib.parse
import urllib.request

from EDMCLogging import get_main_logger
from config import appname, config
from constants import protocolhandler_redirect

logger = get_main_logger()

is_wine = False

if sys.platform == 'win32':
    from ctypes import windll  # type: ignore
    try:
        is_wine = windll.ntdll.wine_get_version
    except Exception:
        pass


class GenericProtocolHandler(object):

    def __init__(self):
        self.redirect = protocolhandler_redirect  # Base redirection URL
        self.master = None
        self.lastpayload = None

    def start(self, master):
        self.master = master

    def close(self):
        pass

    def event(self, url):
        self.lastpayload = url

        if not config.shutting_down:
            self.master.event_generate('<<CompanionAuthEvent>>', when="tail")


if sys.platform == 'darwin' and getattr(sys, 'frozen', False):

    import struct

    import objc
    from AppKit import NSAppleEventManager, NSObject

    kInternetEventClass = kAEGetURL = struct.unpack('>l', b'GURL')[0]
    keyDirectObject = struct.unpack('>l', b'----')[0]

    class DarwinProtocolHandler(GenericProtocolHandler):
        POLL = 100  # ms

        def start(self, master):
            GenericProtocolHandler.start(self, master)
            self.lasturl: Optional[str] = None
            self.eventhandler = EventHandler.alloc().init()

        def poll(self):
            # No way of signalling to Tkinter from within the callback handler block that doesn't cause Python to crash,
            # so poll. TODO: Resolved?
            if self.lasturl and self.lasturl.startswith(self.redirect):
                self.event(self.lasturl)
                self.lasturl = None

    class EventHandler(NSObject):

        def init(self):
            self = objc.super(EventHandler, self).init()
            NSAppleEventManager.sharedAppleEventManager().setEventHandler_andSelector_forEventClass_andEventID_(
                self,
                'handleEvent:withReplyEvent:',
                kInternetEventClass,
                kAEGetURL
            )
            return self

        def handleEvent_withReplyEvent_(self, event, replyEvent):
            protocolhandler.lasturl = urllib.parse.unquote(
                event.paramDescriptorForKeyword_(keyDirectObject).stringValue()).strip()
            protocolhandler.master.after(ProtocolHandler.POLL, protocolhandler.poll)


elif sys.platform == 'win32' and getattr(sys, 'frozen', False) and not is_wine and not config.auth_force_localserver:
    # spell-checker: words HBRUSH HICON WPARAM wstring WNDCLASS HMENU HGLOBAL
    from ctypes import windll  # type: ignore
    from ctypes import POINTER, WINFUNCTYPE, Structure, byref, c_long, c_void_p, create_unicode_buffer, wstring_at
    from ctypes.wintypes import (
        ATOM, BOOL, DWORD, HBRUSH, HGLOBAL, HICON, HINSTANCE, HMENU, HWND, INT, LPARAM, LPCWSTR, LPVOID, LPWSTR, MSG,
        UINT, WPARAM
    )

    class WNDCLASS(Structure):
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

    CreateWindowEx = windll.user32.CreateWindowExW
    CreateWindowEx.argtypes = [DWORD, LPCWSTR, LPCWSTR, DWORD, INT, INT, INT, INT, HWND, HMENU, HINSTANCE, LPVOID]
    CreateWindowEx.restype = HWND
    RegisterClass = windll.user32.RegisterClassW
    RegisterClass.argtypes = [POINTER(WNDCLASS)]
    DefWindowProc = windll.user32.DefWindowProcW
    GetParent = windll.user32.GetParent
    SetForegroundWindow = windll.user32.SetForegroundWindow

    GetMessage = windll.user32.GetMessageW
    TranslateMessage = windll.user32.TranslateMessage
    DispatchMessage = windll.user32.DispatchMessageW
    PostThreadMessage = windll.user32.PostThreadMessageW
    SendMessage = windll.user32.SendMessageW
    SendMessage.argtypes = [HWND, UINT, WPARAM, LPARAM]
    PostMessage = windll.user32.PostMessageW
    PostMessage.argtypes = [HWND, UINT, WPARAM, LPARAM]

    WM_QUIT = 0x0012
    # https://docs.microsoft.com/en-us/windows/win32/dataxchg/wm-dde-initiate
    WM_DDE_INITIATE = 0x03E0
    WM_DDE_TERMINATE = 0x03E1
    WM_DDE_ACK = 0x03E4
    WM_DDE_EXECUTE = 0x03E8

    PackDDElParam = windll.user32.PackDDElParam
    PackDDElParam.argtypes = [UINT, LPARAM, LPARAM]

    GlobalAddAtom = windll.kernel32.GlobalAddAtomW
    GlobalAddAtom.argtypes = [LPWSTR]
    GlobalAddAtom.restype = ATOM
    GlobalGetAtomName = windll.kernel32.GlobalGetAtomNameW
    GlobalGetAtomName.argtypes = [ATOM, LPWSTR, INT]
    GlobalGetAtomName.restype = UINT
    GlobalLock = windll.kernel32.GlobalLock
    GlobalLock.argtypes = [HGLOBAL]
    GlobalLock.restype = LPVOID
    GlobalUnlock = windll.kernel32.GlobalUnlock
    GlobalUnlock.argtypes = [HGLOBAL]
    GlobalUnlock.restype = BOOL

    @WINFUNCTYPE(c_long, HWND, UINT, WPARAM, LPARAM)
    def WndProc(hwnd: HWND, message: UINT, wParam, lParam):  # noqa: N803 N802
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
            return DefWindowProc(hwnd, message, wParam, lParam)

        service = create_unicode_buffer(256)
        topic = create_unicode_buffer(256)
        # Note that lParam is 32 bits, and broken into two 16 bit words. This will break on 64bit as the math is
        # wrong
        lparam_low = lParam & 0xFFFF  # if nonzero, the target application for which a conversation is requested
        lparam_high = lParam >> 16  # if nonzero, the topic of said conversation

        # if either of the words are nonzero, they contain
        # atoms https://docs.microsoft.com/en-us/windows/win32/dataxchg/about-atom-tables
        # which we can read out as shown below, and then compare.

        target_is_valid = lparam_low == 0 or (
            GlobalGetAtomName(lparam_low, service, 256) and service.value == appname
        )

        topic_is_valid = lparam_high == 0 or (
            GlobalGetAtomName(lparam_high, topic, 256) and topic.value.lower() == 'system'
        )

        if target_is_valid and topic_is_valid:
            # if everything is happy, send an acknowledgement of the DDE request
            SendMessage(
                wParam, WM_DDE_ACK, hwnd, PackDDElParam(WM_DDE_ACK, GlobalAddAtom(appname), GlobalAddAtom('System'))
            )
            return 0

    class WindowsProtocolHandler(GenericProtocolHandler):
        """
        Windows implementation of GenericProtocolHandler.

        This works by using windows Dynamic Data Exchange to pass messages between processes
        https://en.wikipedia.org/wiki/Dynamic_Data_Exchange
        """

        def __init__(self):
            GenericProtocolHandler.__init__(self)
            self.thread = None

        def start(self, master):
            """Start the DDE thread."""
            GenericProtocolHandler.start(self, master)
            self.thread = threading.Thread(target=self.worker, name='DDE worker')
            self.thread.daemon = True
            self.thread.start()

        def close(self):
            """Stop the DDE thread"""
            thread = self.thread
            if thread:
                self.thread = None
                PostThreadMessage(thread.ident, WM_QUIT, 0, 0)
                thread.join()  # Wait for it to quit

        def worker(self):
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

            if RegisterClass(byref(wndclass)):
                hwnd = CreateWindowEx(
                    0,
                    wndclass.lpszClassName,
                    "DDE Server",
                    0,
                    CW_USEDEFAULT, CW_USEDEFAULT, CW_USEDEFAULT, CW_USEDEFAULT,
                    self.master.winfo_id(),  # Don't use HWND_MESSAGE since the window won't get DDE broadcasts
                    None,
                    wndclass.hInstance,
                    None
                )

                msg = MSG()
                while GetMessage(byref(msg), None, 0, 0) != 0:
                    logger.trace(f'DDE message of type: {msg.message}')
                    if msg.message == WM_DDE_EXECUTE:
                        args = wstring_at(GlobalLock(msg.lParam)).strip()
                        GlobalUnlock(msg.lParam)
                        if args.lower().startswith('open("') and args.endswith('")'):
                            logger.trace(f'args are: {args}')
                            url = urllib.parse.unquote(args[6:-2]).strip()
                            logger.trace(f'Parsed url: {url}')
                            if url.startswith(self.redirect):
                                logger.debug(f'Message starts with {self.redirect}')
                                self.event(url)

                            SetForegroundWindow(GetParent(self.master.winfo_id()))  # raise app window
                            PostMessage(msg.wParam, WM_DDE_ACK, hwnd, PackDDElParam(WM_DDE_ACK, 0x80, msg.lParam))

                        else:
                            PostMessage(msg.wParam, WM_DDE_ACK, hwnd, PackDDElParam(WM_DDE_ACK, 0, msg.lParam))

                    elif msg.message == WM_DDE_TERMINATE:
                        PostMessage(msg.wParam, WM_DDE_TERMINATE, hwnd, 0)

                    else:
                        TranslateMessage(byref(msg))
                        DispatchMessage(byref(msg))

            else:
                print('Failed to register DDE for cAPI')

else:  # Linux / Run from source

    from http.server import BaseHTTPRequestHandler, HTTPServer

    class LinuxProtocolHandler(GenericProtocolHandler):
        """
        Implementation of GenericProtocolHandler.

        This implementation uses a localhost HTTP server
        """

        def __init__(self):
            GenericProtocolHandler.__init__(self)
            self.httpd = HTTPServer(('localhost', 0), HTTPRequestHandler)
            self.redirect = 'http://localhost:%d/auth' % self.httpd.server_port
            logger.trace(f'Web server listening on {self.redirect}')
            self.thread = None

        def start(self, master):
            """Start the HTTP server thread."""
            GenericProtocolHandler.start(self, master)
            self.thread = threading.Thread(target=self.worker, name='OAuth worker')
            self.thread.daemon = True
            self.thread.start()

        def close(self):
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

        def worker(self):
            """HTTP Worker."""
            # TODO: This should probably be more ephemeral, and only handle one request, as its all we're expecting
            self.httpd.serve_forever()

    class HTTPRequestHandler(BaseHTTPRequestHandler):
        """Simple HTTP server to handle IPC from protocol handler."""

        def parse(self):
            """Parse a request."""
            url = urllib.parse.unquote(self.path)
            if url.startswith('/auth'):
                logger.debug('Request starts with /auth, sending to protocolhandler.event()')
                protocolhandler.event(url)
                self.send_response(200)
                return True
            else:
                self.send_response(404)  # Not found
                return False

        def do_HEAD(self):  # noqa: N802 # Required to override
            """Handle HEAD Request."""
            self.parse()
            self.end_headers()

        def do_GET(self):  # noqa: N802 # Required to override
            """Handle GET Request."""
            if self.parse():
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write('<html><head><title>Authentication successful</title></head>'.encode('utf-8'))
                self.wfile.write('<body><p>Authentication successful</p></body>'.encode('utf-8'))
            else:
                self.end_headers()

        def log_request(self, code, size=None):
            """Override to prevent logging."""
            pass


# singleton
protocolhandler: GenericProtocolHandler

if sys.platform == 'darwin' and getattr(sys, 'frozen', False):
    protocolhandler = DarwinProtocolHandler()  # pyright: reportUnboundVariable=false

elif sys.platform == 'win32' and getattr(sys, 'frozen', False) and not is_wine:
    protocolhandler = WindowsProtocolHandler()
else:
    protocolhandler = LinuxProtocolHandler()
