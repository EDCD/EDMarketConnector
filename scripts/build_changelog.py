#!/usr/bin/env python3
# flake8: noqa
"""
build_changelog.py - Read the latest changelog file and format for the Forums and Reddit.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.
"""

import pathlib
import re
from os import chdir
import mistune


def get_changelog() -> tuple[str, str]:
    """Pull the last full changelog details in MD."""
    try:
        with open("../CHANGELOG.md", encoding="utf-8") as changelog_file:
            content = changelog_file.read()
    except FileNotFoundError as exc:
        raise FileNotFoundError("Changelog file not found.") from exc

    changelog_list = content.split("---", maxsplit=2)
    if len(changelog_list) < 3:
        raise ValueError("Changelog format is incorrect.")

    changelog = changelog_list[2].split("===", maxsplit=2)
    if len(changelog) < 2:
        raise ValueError("Changelog format is incorrect.")

    changelog[0] = changelog[0].strip()
    changelog[1] = "\n".join(changelog[1].strip().split("\n")[:-2])
    version = changelog[0]
    version = version.split(" ")[1]
    final_changelog = changelog[1].strip()

    return final_changelog, version


def build_html(md_changelog: str, version: str) -> str:
    """Convert markdown changelog to HTML."""
    html_out = f"<h2>Release {version}</h2>\n"
    html_out += mistune.html(md_changelog)  # type: ignore
    html_out = re.sub(r"h1", "h2", html_out) + "\n<hr>"

    with open("script_output/html_changelog.txt", "w", encoding="utf-8") as html_file:
        html_file.write(html_out)

    return html_out


def format_fdev(md_log: str) -> str:
    """Format changelog for FDEV forums."""
    md_log = re.sub(r"<p>|</p>", "", md_log)
    md_log = re.sub(r"<strong>", "\n[HEADING=3]", md_log)
    md_log = re.sub(r"</strong>", "[/HEADING]", md_log)
    md_log = re.sub(r"<ul>", "[LIST]", md_log)
    md_log = re.sub(r"<li>", "[*]", md_log)
    md_log = re.sub(r"</li>", "", md_log)
    md_log = re.sub(r"<code>", "[ICODE]", md_log)
    md_log = re.sub(r"</code>", "[/ICODE]", md_log)
    md_log = re.sub(r"</ul>\n", "[/LIST]", md_log)
    md_log = re.sub(r"<hr>", "", md_log)
    md_log = re.sub(r"Changes and Enhancements", "What's Changed", md_log)
    return md_log


def build_fdev(
    vt_signed: str, vt_unsigned: str, version: str, gh_link: str, html: str
) -> None:
    """Build changelog for FDEV forums."""
    fdev_out = (
        f"[HEADING=2][URL='{gh_link}'][SIZE=7]Release {version}[/SIZE][/URL][/HEADING]\n"
        f"[URL='{vt_signed}']Pre-emptive upload to VirusTotal[/URL]. "
        f"([URL='{vt_unsigned}']Unsigned Installer[/URL])\n\n"
    )

    if version.startswith(("Pre-Release", "Beta")):
        fdev_out += (
            f'This is a release candidate for {version}. It has been pushed to the "Beta" track for updates!\n\n'
            'For more information on the "Beta" update track, please read '
            "[URL='https://github.com/EDCD/EDMarketConnector/wiki/Participating-in-Open-Betas-of-EDMC']"
            "This Wiki Article[/URL]. Questions and comments are welcome!\n\n"
        )

    md_log = html.split("\n", maxsplit=1)[1]
    md_log = format_fdev(md_log)
    fdev_out += md_log

    with open("script_output/fdev_changelog.txt", "w", encoding="utf-8") as fdev_file:
        fdev_file.write(fdev_out)


def build_reddit(
    md_changelog: str, vt_signed: str, vt_unsigned: str, version: str, gh_link: str
) -> None:
    """Build changelog for Reddit."""
    reddit_start = """# What Is Elite Dangerous Market Connector?

Elite Dangerous Market Connector ("EDMC") is a third-party application for use with Frontier Developments' game "Elite Dangerous". Its purpose is to facilitate supplying certain game data to, and in some cases retrieving it from, a number of websites and other tools.

To achieve this it utilizes the Journal Files written by the game when played on a PC. It also makes use of Frontier's Companion API  ("Frontier's CAPI"), accessible once you've authorized this application.

EDMC has a plugin system that many other developers have made use of to extend its functionality.

Find out more on the [EDMC Wiki](https://github.com/EDCD/EDMarketConnector/wiki).

~~----------------------------------------------------~~

You can also view the Elite: Dangerous Forum thread [HERE](https://forums.frontier.co.uk/threads/elite-dangerous-market-connector-edmc.618708/).

~~----------------------------------------------------~~

**As has become routine now, various anti-virus software are reporting a false positive on our installer and/or files it contains. We've pre-emptively uploaded the installer to** [VirusTotal]("""
    reddit_mid_1 = """) **if you want to check what it's saying. Please see our** [Troubleshooting/AV-false-positives FAQ](https://github.com/EDCD/EDMarketConnector/wiki/Troubleshooting#installer-and-or-executables-flagged-as-malicious-viruses) **for further information.**

[Unsigned Installer]("""

    reddit_mid_2 = """) if you don't want to use the code-signed option.

~~----------------------------------------------------~~
"""
    updated = f"# [Release {version}]({gh_link})\n\n"
    md_changelog = re.sub(r"===\n", "", md_changelog)
    md_changelog = re.sub(f"Release {version}", updated, md_changelog)
    reddit_end = f"""

**Linux**

If you're running on Linux, try the [Flatpak](https://flathub.org/apps/io.edcd.EDMarketConnector) build of EDMC! (Update to {version} coming soon.)"""

    reddit_out = (
        reddit_start
        + vt_signed
        + reddit_mid_1
        + vt_unsigned
        + reddit_mid_2
        + updated
        + md_changelog
        + reddit_end
    )

    with open(
        "script_output/reddit_changelog.txt", "w", encoding="utf-8"
    ) as reddit_file:
        reddit_file.write(reddit_out)


def main() -> None:
    """Run the Changelog Generator"""
    md_changelog, version = get_changelog()
    print(f"Detected version {version} in the changelog. Continuing...")
    gh_link = input(f"Please enter the GitHub link for {version}: ")
    vt_signed = input("Please enter the VirusTotal URL for the Signed Installer: ")
    vt_unsigned = input("Please enter the VirusTotal URL for the Unsigned Installer: ")
    build_reddit(md_changelog, vt_signed, vt_unsigned, version, gh_link)
    html = build_html(md_changelog, version)
    build_fdev(vt_signed, vt_unsigned, version, gh_link, html)


if __name__ == "__main__":
    chdir(pathlib.Path(__file__).parent)
    main()
