"""Simple HTTP listener to be used with debugging various EDMC sends."""
from __future__ import annotations

import gzip
import json
import pathlib
import threading
import zlib
from http import server
from typing import Any, Literal
from collections.abc import Callable
from urllib.parse import parse_qs
from config import config
from EDMCLogging import get_main_logger

logger = get_main_logger()

output_lock = threading.Lock()
output_data_path = pathlib.Path(config.app_dir_path / 'logs' / 'http_debug')  # type: ignore
SAFE_TRANSLATE = str.maketrans(dict.fromkeys("!@#$%^&*()./\\\r\n[]-+='\";:?<>,~`", '_'))


class LoggingHandler(server.BaseHTTPRequestHandler):
    """HTTP Handler implementation that logs to EDMCs logger and writes data to files on disk."""

    def log_message(self, format: str, *args: Any) -> None:
        """Override default handler logger with EDMC logger."""
        logger.info(format % args)

    def do_POST(self) -> None:  # noqa: N802 # I cant change it
        """Handle POST."""
        logger.info(f"Received a POST for {self.path!r}!")
        data_raw: bytes = self.rfile.read(int(self.headers['Content-Length']))

        encoding = self.headers.get('Content-Encoding')

        to_save = data = self.get_printable(data_raw, encoding)

        target_path = self.path
        if len(target_path) > 1 and target_path[0] == '/':
            target_path = target_path[1:]

        elif len(target_path) == 1 and target_path[0] == '/':
            target_path = 'WEB_ROOT'

        response: Callable[[str], str] | str | None = DEFAULT_RESPONSES.get(target_path)
        if callable(response):
            response = response(to_save)

        self.send_response_only(200, "OK")
        if response is not None:
            self.send_header('Content-Length', str(len(response)))

        self.end_headers()  # This is needed because send_response_only DOESN'T ACTUALLY SEND THE RESPONSE </rant>
        if response is not None:
            self.wfile.write(response.encode())
            self.wfile.flush()

        if target_path == 'edsm':
            # attempt to extract data from urlencoded stream
            try:
                edsm_data = extract_edsm_data(data)
                data = data + "\n" + json.dumps(edsm_data)
            except Exception:
                pass

        target_file = output_data_path / (safe_file_name(target_path) + '.log')
        if target_file.parent != output_data_path:
            logger.warning(f"REFUSING TO WRITE FILE THAT ISN'T IN THE RIGHT PLACE! {target_file=}")
            logger.warning(f'DATA FOLLOWS\n{data}')
            return

        with output_lock, target_file.open('a') as file:
            file.write(to_save + "\n\n")

    @staticmethod
    def get_printable(data: bytes, compression: Literal['deflate'] | Literal['gzip'] | str | None = None) -> str:
        """
        Convert an incoming data stream into a string.

        :param data: The data to convert
        :param compression: The compression to remove, defaults to None
        :raises ValueError: If compression is unknown
        :return: printable strings
        """
        ret: bytes = b''
        if compression is None:
            ret = data

        elif compression == 'deflate':
            ret = zlib.decompress(data)

        elif compression == 'gzip':
            ret = gzip.decompress(data)

        else:
            raise ValueError(f'Unknown encoding for data {compression!r}')

        return ret.decode('utf-8', errors='replace')


def safe_file_name(name: str):
    """
    Escape special characters out of a file name.

    This is a nicety. Don't rely on it to be ultra secure.
    """
    return name.translate(SAFE_TRANSLATE)


def generate_inara_response(raw_data: str) -> str:
    """Generate nonstatic data for inara plugin."""
    try:
        data = json.loads(raw_data)
    except json.JSONDecodeError:
        return "UNKNOWN REQUEST"

    out = {
        'header': {
            'eventStatus': 200
        },

        'events': [
            {
                'eventName': e['eventName'], 'eventStatus': 200, 'eventStatusText': "DEBUG STUFF"
            } for e in data.get('events')
        ]
    }

    return json.dumps(out)


def extract_edsm_data(data: str) -> dict[str, Any]:
    """Extract relevant data from edsm data."""
    res = parse_qs(data)
    return {name: data[0] for name, data in res.items()}


def generate_edsm_response(raw_data: str) -> str:
    """Generate nonstatic data for edsm plugin."""
    try:
        data = extract_edsm_data(raw_data)
        events = json.loads(data['message'])
    except (json.JSONDecodeError, Exception):
        logger.exception("????")
        return "UNKNOWN REQUEST"

    out = {
        'msgnum': 100,  # Ok
        'msg': 'debug stuff',
        'events': [
            {'event': e['event'], 'msgnum': 100, 'msg': 'debug stuff'} for e in events
        ]
    }

    return json.dumps(out)


DEFAULT_RESPONSES = {
    'inara': generate_inara_response,
    'edsm': generate_edsm_response
}


def run_listener(host: str = "127.0.0.1", port: int = 9090) -> None:
    """Run a listener thread."""
    output_data_path.mkdir(exist_ok=True)
    logger.info(f'Starting HTTP listener on {host=} {port=}!')
    listener = server.HTTPServer((host, port), LoggingHandler)
    logger.info(listener)
    threading.Thread(target=listener.serve_forever, daemon=True).start()


if __name__ == "__main__":
    output_data_path.mkdir(exist_ok=True)
    server.HTTPServer(("127.0.0.1", 9090), LoggingHandler).serve_forever()
