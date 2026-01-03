"""
update.py - Checking for Program Updates.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License v2 or later.
See LICENSE file.
"""
from __future__ import annotations

import pathlib
import hashlib
import shutil
import sys
import threading
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from tkinter import messagebox
from traceback import print_exc
from typing import TYPE_CHECKING, cast, Any
from xml.etree import ElementTree
import requests
import semantic_version
from config import appname, appversion_nobuild, config, get_update_feed
from EDMCLogging import get_main_logger
from l10n import translations as tr

if TYPE_CHECKING:
    import tkinter as tk

logger = get_main_logger()

HTTP_TIMEOUT = (5, 20)          # (connect, read)
HTTP_RETRIES = 3
RETRY_BACKOFF = 1.5             # seconds multiplier
MAX_WORKERS = 8


def read_normalized_file(path: pathlib.Path) -> tuple[str, str, str] | None:
    """Read a UTF-8 (with BOM-safe) file and normalize line endings and whitespace."""
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None
    newline = '\r\n' if b'\r\n' in raw else '\n'
    text = raw.decode('utf-8-sig')
    normalized = text.replace('\r\n', '\n').strip()

    return normalized, hashlib.sha256(normalized.encode()).hexdigest(), newline


def copy_bundle_file(filename: str, dest_dir: pathlib.Path) -> tuple[str, str] | None:
    """
    Attempt to copy a missing file from the bundled FDevIDs folder.

    Returns (content, hash) or None.
    """
    try:
        dest = dest_dir / filename
        shutil.copy(f"FDevIDs/{filename}", dest)
        return read_normalized_file(dest)  # type: ignore
    except (FileNotFoundError, shutil.SameFileError):
        logger.info("Bundle copy failed or identical; continuing with empty content.")
        return None


def fetch_remote_file(url: str) -> tuple[str, str] | None:
    """
    Fetch a remote file with retries.

    Returns (normalized_text, hash) or None on failure.
    """
    delay = 1.0

    for attempt in range(1, HTTP_RETRIES + 1):
        try:
            response = requests.get(url, timeout=HTTP_TIMEOUT)
            response.raise_for_status()

            text = response.text.replace('\r\n', '\n').strip()
            return text, hashlib.sha256(text.encode()).hexdigest()

        except requests.RequestException as exc:
            if attempt >= HTTP_RETRIES:
                logger.debug("Download failed after %d attempts: %s", attempt, exc)
                return None

            time.sleep(delay)
            delay *= RETRY_BACKOFF
    return None


def update_single_file(
    directory: pathlib.Path,
    filename: str,
    url: str,
    silent: bool = False,
) -> None:
    """Update a single bundle file."""
    file_path = directory / filename

    local = read_normalized_file(file_path)
    if local is None:
        local = copy_bundle_file(filename, directory)  # type: ignore

    if local:
        local_text, local_hash, newline = local
    else:
        local_text, local_hash, newline = '', '', '\n'  # noqa: F841

    remote = fetch_remote_file(url)
    if not remote:
        if not silent:
            logger.error(f'Failed to download {filename}! Unable to continue.')
        return

    remote_text, remote_hash = remote

    if local_hash == remote_hash:
        if not silent:
            logger.info(f'{filename} already up to date.')
        return

    if not silent:
        logger.info(f'Updating file {filename}...')

    # Restore original newline style
    output = remote_text.replace('\n', newline)
    file_path.write_text(output, encoding='utf-8', newline='')


def update_files(
    directory: pathlib.Path,
    files_urls: dict[str, str],
    silent: bool = False,
) -> None:
    """Start threads to update bundle files."""
    directory.mkdir(parents=True, exist_ok=True)

    max_workers = min(MAX_WORKERS, len(files_urls))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(update_single_file, directory, filename, url, silent)
            for filename, url in files_urls.items()
        ]

        for future in as_completed(futures):
            try:
                future.result()
            except Exception:
                logger.exception("Unexpected error while updating files")


def check_for_fdev_updates(silent: bool = False, local: bool = False) -> None:
    """Check for and download FDEV ID file updates."""
    base_path = config.respath_path if local else config.app_dir_path
    fdevid_dir = pathlib.Path(base_path, 'FDevIDs')
    fdevid_dir.mkdir(parents=True, exist_ok=True)

    files_urls = {
        'commodity.csv': 'https://raw.githubusercontent.com/EDCD/FDevIDs/master/commodity.csv',
        'rare_commodity.csv': 'https://raw.githubusercontent.com/EDCD/FDevIDs/master/rare_commodity.csv'
    }
    if not silent:
        logger.info(f"Checking for {'local ' if local else ''}FDEVID file updates...")
    update_files(fdevid_dir, files_urls, silent)


def check_for_datafile_updates(silent: bool = False, local: bool = False) -> None:
    """Check for and download data file updates."""
    base_path = config.respath_path if local else config.app_dir_path
    files_urls = {
        'modules.json': 'https://raw.githubusercontent.com/EDCD/EDMarketConnector/refs/heads/releases/modules.json',
        'ships.json': 'https://raw.githubusercontent.com/EDCD/EDMarketConnector/refs/heads/releases/ships.json',
        'master_plugin_list.json': 'https://raw.githubusercontent.com/Rixxan/'
                                   'EDMC_Plugin_Registry_Dev/refs/heads/master/master_plugin_list.json'
    }
    if not silent:
        logger.info(f"Checking for {'local ' if local else ''}datafile file updates...")
    update_files(pathlib.Path(base_path), files_urls, silent)


@dataclass(slots=True)
class EDMCVersion:
    """
    Hold all the information about an EDMC version.

    Attributes
    ----------
    version : str
        Full version string
    title: str
        Title of the release
    sv: semantic_version.base.Version
        semantic_version object for this version
    """

    version: str
    title: str
    sv: semantic_version.Version


class Updater:
    """
    Handle checking for updates.

    This is used whether using internal code or an external library such as
    WinSparkle on win32.
    """

    def __init__(self, tkroot: tk.Tk | None = None, provider: str = 'internal'):
        """
        Initialise an Updater instance.

        :param tkroot: reference to the root window of the GUI
        :param provider: 'internal' or other string if not
        """
        self.root: tk.Tk | None = tkroot
        self.provider: str = provider
        self.thread: threading.Thread | None = None
        self.updater: Any | None = None  # ensure attribute exists

        if not self.use_internal() and sys.platform == 'win32':
            self._init_winsparkle()

    def start_check_thread(self) -> None:
        """Start the background update worker thread safely."""
        if self.use_internal():
            self.thread = threading.Thread(
                target=self.worker,
                name='update worker',
                daemon=True
            )
            self.thread.start()
        else:
            if sys.platform == 'win32' and self.updater:
                self.updater.win_sparkle_check_update_with_ui()

        # Always trigger FDEV checks here too
        check_for_fdev_updates()
        check_for_datafile_updates()
        try:
            check_for_fdev_updates(local=True)
            check_for_datafile_updates(local=True)
        except Exception as e:
            logger.info(
                "Tried to update bundle files but failed. Don't worry, "
                "this likely isn't important and can be ignored unless "
                f"you run into other issues. If you're curious: {e}"
            )

    def shutdown_request(self) -> None:
        """Receive (Win)Sparkle shutdown request and send it to parent."""
        if not config.shutting_down and self.root:
            self.root.event_generate('<<Quit>>', when="tail")

    def use_internal(self) -> bool:
        """
        Signal if internal update checks should be used.

        :return: bool
        """
        return self.provider == 'internal'

    def _init_winsparkle(self) -> None:
        """Initialize WinSparkle updater for Windows."""
        import ctypes
        try:
            self.updater = cast(ctypes.CDLL, ctypes.cdll.WinSparkle)
            self.updater.win_sparkle_set_appcast_url(get_update_feed().encode())  # Set the appcast URL

            # Set the appversion *without* build metadata, as WinSparkle
            # doesn't do proper Semantic Version checks.
            # NB: It 'accidentally' supports pre-release due to how it
            # splits and compares strings:
            # <https://github.com/vslavik/winsparkle/issues/214>
            self.updater.win_sparkle_set_app_build_version(str(appversion_nobuild()))

            # set up shutdown callback
            self.callback_t = ctypes.CFUNCTYPE(None)  # keep reference
            self.callback_fn = self.callback_t(self.shutdown_request)
            self.updater.win_sparkle_set_shutdown_request_callback(self.callback_fn)

            # Get WinSparkle running
            self.updater.win_sparkle_init()

        except Exception:
            print_exc()
            self.updater = None
            msg = "Updater Failed to Initialize. Please file a bug report!"
            if not os.getenv("EDMC_NO_UI"):
                messagebox.showerror(title=appname, message=msg)
            else:
                logger.error(msg)

    def set_automatic_updates_check(self, onoroff: bool) -> None:
        """
        Set (Win)Sparkle to perform automatic update checks, or not.

        :param onoroff: bool for if we should have the library check or not.
        """
        if self.use_internal():
            return

        if sys.platform == 'win32' and self.updater:
            self.updater.win_sparkle_set_automatic_check_for_updates(onoroff)

    def check_for_updates(self) -> None:
        """Trigger the requisite method to check for an update."""
        if self.use_internal():
            self.thread = threading.Thread(target=self.worker, name='update worker', daemon=True)
            self.thread.start()
        elif sys.platform == 'win32' and self.updater:
            self.updater.win_sparkle_check_update_with_ui()

        check_for_fdev_updates()
        check_for_datafile_updates()
        try:
            check_for_fdev_updates(local=True)
            check_for_datafile_updates(local=True)
        except Exception as e:
            logger.info("Tried to update bundle files but failed. Don't worry, "
                        "this likely isn't important and can be ignored unless"
                        f" you run into other issues. If you're curious: {e}")

    def check_appcast(self) -> EDMCVersion | None:
        """
        Manually (no Sparkle or WinSparkle) check the get_update_feed() appcast file.

        Checks if any listed version is semantically greater than the current
        running version.
        :return: EDMCVersion or None if no newer version found
        """
        newversion = None
        items = {}
        try:
            request = requests.get(get_update_feed(), timeout=10)

        except requests.RequestException as ex:
            logger.exception(f'Error retrieving update_feed file: {ex}')
            return None

        try:
            feed = ElementTree.fromstring(request.text)

        except SyntaxError as ex:
            logger.exception(f'Syntax error in update_feed file: {ex}')
            return None

        # For *these* purposes all systems are the same as 'windows', as
        # non-win32 would be running from source.
        sparkle_platform = 'windows'

        for item in feed.findall('channel/item'):
            # xml is a pain with types, hence these ignores
            ver = item.find('enclosure').attrib.get(  # type: ignore
                '{http://www.andymatuschak.org/xml-namespaces/sparkle}version'
            )
            ver_platform = item.find('enclosure').attrib.get(  # type: ignore
                '{http://www.andymatuschak.org/xml-namespaces/sparkle}os'
            )
            if ver_platform != sparkle_platform:
                continue

            # This will change A.B.C.D to A.B.C+D
            semver = semantic_version.Version.coerce(ver)

            items[semver] = EDMCVersion(
                version=str(ver),  # sv might have mangled version
                title=item.find('title').text,  # type: ignore
                sv=semver
            )

        # Look for any remaining version greater than appversion
        simple_spec = semantic_version.SimpleSpec(f'>{appversion_nobuild()}')
        newversion = simple_spec.select(items.keys())
        return items[newversion] if newversion else None

    def worker(self) -> None:
        """Perform internal update checking & update GUI status if needs be."""
        newversion = self.check_appcast()

        if newversion and self.root:
            self.root.after(0, self._set_update_status, newversion.title)
        else:
            logger.info("No new version available at this time")

    def _set_update_status(self, newver_title: str) -> None:
        if not self.root:
            return
        status = self.root.nametowidget(f'.{appname.lower()}.status')
        # LANG: Update Available Text
        status['text'] = tr.tl("{NEWVER} is available").format(NEWVER=newver_title)
        self.root.update_idletasks()

    def close(self) -> None:
        """
        Handle the EDMarketConnector.AppWindow.onexit() request.

        NB: We just 'pass' here because:
         1) We might have a worker() going, but no way to make that
            co-operative to respond to a "please stop now" message.
         2) If we're running frozen then we're using (Win)Sparkle to check
            and *it* might have asked this whole application to quit, in
            which case we don't want to ask *it* to quit
        """
        pass
