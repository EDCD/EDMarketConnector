"""Simple HTTP listener to be used with debugging EDDN sends."""
import threading
from http import server
from typing import Any

from EDMCLogging import get_main_logger

logger = get_main_logger()


class LoggingHandler(server.BaseHTTPRequestHandler):
    """HTTP Handler implementation that logs to EDMCs logger."""

    def log_message(self, format: str, *args: Any) -> None:
        """Override default handler logger with EDMC logger."""
        logger.info(format % args)

    def do_POST(self) -> None:  # noqa: N802 # I cant change it
        """Handle POST."""
        logger.info("Received a POST!")
        data = self.rfile.read(int(self.headers['Content-Length']))
        logger.info(f"POST DATA FOLLOWS\n{data.decode('utf-8', errors='replace')}")
        self.send_response(200, "OK")


def run_listener(port: int = 9090) -> None:
    """Run a listener thread."""
    logger.info('Starting HTTP listener on 127.0.0.1:{port}!')
    listener = server.HTTPServer(("127.0.0.1", port), LoggingHandler)
    threading.Thread(target=listener.serve_forever, daemon=True)


if __name__ == "__main__":
    server.HTTPServer(("127.0.0.1", 8080), LoggingHandler).serve_forever()
