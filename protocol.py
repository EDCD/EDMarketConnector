# edmc: protocol handler for cAPI authorisation


import threading
import urllib.request, urllib.error, urllib.parse
import sys

from config import appname


if sys.platform == 'win32':
    from ctypes import *
    from ctypes.wintypes import *
    try:
        is_wine = windll.ntdll.wine_get_version
    except:
        is_wine = False


class GenericProtocolHandler(object):

    def __init__(self):
        self.redirect = 'edmc://auth'	# Base redirection URL
        self.master = None
        self.lastpayload = None

    def start(self, master):
        self.master = master

    def close(self):
        pass

    def event(self, url):
        self.lastpayload = url
        self.master.event_generate('<<CompanionAuthEvent>>', when="tail")


if sys.platform == 'darwin' and getattr(sys, 'frozen', False):

    import struct
    import objc
    from AppKit import NSAppleEventManager, NSObject

    kInternetEventClass = kAEGetURL = struct.unpack('>l', b'GURL')[0]
    keyDirectObject = struct.unpack('>l', b'----')[0]

    class ProtocolHandler(GenericProtocolHandler):

        POLL = 100	# ms

        def start(self, master):
            GenericProtocolHandler.start(self, master)
            self.lasturl = None
            self.eventhandler = EventHandler.alloc().init()

        def poll(self):
            # No way of signalling to Tkinter from within the callback handler block that doesn't cause Python to crash, so poll.
            if self.lasturl and self.lasturl.startswith(self.redirect):
                self.event(self.lasturl)
                self.lasturl = None

    class EventHandler(NSObject):

        def init(self):
            self = objc.super(EventHandler, self).init()
            NSAppleEventManager.sharedAppleEventManager().setEventHandler_andSelector_forEventClass_andEventID_(self, 'handleEvent:withReplyEvent:', kInternetEventClass, kAEGetURL)
            return self

        def handleEvent_withReplyEvent_(self, event, replyEvent):
            protocolhandler.lasturl = urllib.parse.unquote(event.paramDescriptorForKeyword_(keyDirectObject).stringValue()).strip()
            protocolhandler.master.after(ProtocolHandler.POLL, protocolhandler.poll)


elif sys.platform == 'win32' and getattr(sys, 'frozen', False) and not is_wine:

    class WNDCLASS(Structure):
        _fields_ = [('style', UINT),
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

    CW_USEDEFAULT     = 0x80000000

    CreateWindowEx    = windll.user32.CreateWindowExW
    CreateWindowEx.argtypes = [DWORD, LPCWSTR, LPCWSTR, DWORD, INT, INT, INT, INT, HWND, HMENU, HINSTANCE, LPVOID]
    CreateWindowEx.restype  = HWND
    RegisterClass     = windll.user32.RegisterClassW
    RegisterClass.argtypes  = [POINTER(WNDCLASS)]
    DefWindowProc     = windll.user32.DefWindowProcW
    GetParent         = windll.user32.GetParent
    SetForegroundWindow = windll.user32.SetForegroundWindow

    GetMessage        = windll.user32.GetMessageW
    TranslateMessage  = windll.user32.TranslateMessage
    DispatchMessage   = windll.user32.DispatchMessageW
    PostThreadMessage = windll.user32.PostThreadMessageW
    SendMessage       = windll.user32.SendMessageW
    SendMessage.argtypes = [HWND, UINT, WPARAM, LPARAM]
    PostMessage       = windll.user32.PostMessageW
    PostMessage.argtypes = [HWND, UINT, WPARAM, LPARAM]

    WM_QUIT           = 0x0012
    WM_DDE_INITIATE   = 0x03E0
    WM_DDE_TERMINATE  = 0x03E1
    WM_DDE_ACK        = 0x03E4
    WM_DDE_EXECUTE    = 0x03E8

    PackDDElParam     = windll.user32.PackDDElParam
    PackDDElParam.argtypes = [UINT, LPARAM, LPARAM]

    GlobalAddAtom     = windll.kernel32.GlobalAddAtomW
    GlobalAddAtom.argtypes = [LPWSTR]
    GlobalAddAtom.restype = ATOM
    GlobalGetAtomName = windll.kernel32.GlobalGetAtomNameW
    GlobalGetAtomName.argtypes = [ATOM, LPWSTR, INT]
    GlobalGetAtomName.restype = UINT
    GlobalLock        = windll.kernel32.GlobalLock
    GlobalLock.argtypes = [HGLOBAL]
    GlobalLock.restype = LPVOID
    GlobalUnlock      = windll.kernel32.GlobalUnlock
    GlobalUnlock.argtypes = [HGLOBAL]
    GlobalUnlock.restype = BOOL


    @WINFUNCTYPE(c_long, HWND, UINT, WPARAM, LPARAM)
    def WndProc(hwnd, message, wParam, lParam):
        service = create_unicode_buffer(256)
        topic = create_unicode_buffer(256)
        if message == WM_DDE_INITIATE:
            if ((lParam & 0xffff == 0 or (GlobalGetAtomName(lParam & 0xffff, service, 256) and service.value == appname)) and
                (lParam >> 16 == 0 or (GlobalGetAtomName(lParam >> 16, topic, 256) and topic.value.lower() == 'system'))):
                SendMessage(wParam, WM_DDE_ACK, hwnd, PackDDElParam(WM_DDE_ACK, GlobalAddAtom(appname), GlobalAddAtom('System')))
                return 0
        return DefWindowProc(hwnd, message, wParam, lParam)


    class ProtocolHandler(GenericProtocolHandler):

        def __init__(self):
            GenericProtocolHandler.__init__(self)
            self.thread = None

        def start(self, master):
            GenericProtocolHandler.start(self, master)
            self.thread = threading.Thread(target=self.worker, name='DDE worker')
            self.thread.daemon = True
            self.thread.start()

        def close(self):
            thread = self.thread
            if thread:
                self.thread = None
                PostThreadMessage(thread.ident, WM_QUIT, 0, 0)
                thread.join()	# Wait for it to quit

        def worker(self):
            wndclass = WNDCLASS()
            wndclass.style          = 0
            wndclass.lpfnWndProc    = WndProc
            wndclass.cbClsExtra     = 0
            wndclass.cbWndExtra     = 0
            wndclass.hInstance      = windll.kernel32.GetModuleHandleW(0)
            wndclass.hIcon          = None
            wndclass.hCursor        = None
            wndclass.hbrBackground  = None
            wndclass.lpszMenuName   = None
            wndclass.lpszClassName  = 'DDEServer'

            if RegisterClass(byref(wndclass)):
                hwnd = CreateWindowEx(0,
                                      wndclass.lpszClassName,
                                      "DDE Server",
                                      0,
                                      CW_USEDEFAULT, CW_USEDEFAULT, CW_USEDEFAULT, CW_USEDEFAULT,
                                      self.master.winfo_id(),	# Don't use HWND_MESSAGE since the window won't get DDE broadcasts
                                      None,
                                      wndclass.hInstance,
                                      None)
                msg = MSG()
                while GetMessage(byref(msg), None, 0, 0) != 0:
                    if msg.message == WM_DDE_EXECUTE:
                        args = wstring_at(GlobalLock(msg.lParam)).strip()
                        GlobalUnlock(msg.lParam)
                        if args.lower().startswith('open("') and args.endswith('")'):
                            url = urllib.parse.unquote(args[6:-2]).strip()
                            if url.startswith(self.redirect):
                                self.event(url)
                            SetForegroundWindow(GetParent(self.master.winfo_id()))	# raise app window
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

else:	# Linux / Run from source

    from http.server import HTTPServer, BaseHTTPRequestHandler

    class ProtocolHandler(GenericProtocolHandler):

        def __init__(self):
            GenericProtocolHandler.__init__(self)
            self.httpd = HTTPServer(('localhost', 0), HTTPRequestHandler)
            self.redirect = 'http://localhost:%d/auth' % self.httpd.server_port
            self.thread = None

        def start(self, master):
            GenericProtocolHandler.start(self, master)
            self.thread = threading.Thread(target=self.worker, name='OAuth worker')
            self.thread.daemon = True
            self.thread.start()

        def close(self):
            thread = self.thread
            if thread:
                self.thread = None
                if self.httpd:
                    self.httpd.shutdown()
                thread.join()	# Wait for it to quit

        def worker(self):
            self.httpd.serve_forever()

    class HTTPRequestHandler(BaseHTTPRequestHandler):

        def parse(self):
            url = urllib.parse.unquote(self.path)
            if url.startswith('/auth'):
                protocolhandler.event(url)
                self.send_response(200)
                return True
            else:
                self.send_response(404)	# Not found
                return False

        def do_HEAD(self):
            self.parse()
            self.end_headers()

        def do_GET(self):
            if self.parse():
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write('<html><head><title>{}</title></head>'.format('Authentication successful').encode('utf-8'))
                self.wfile.write('<body><p>{}</p></body>'.format('Authentication successful').encode('utf-8'))
            else:
                self.end_headers()

        def log_request(self, code, size=None):
            pass


# singleton
protocolhandler = ProtocolHandler()
