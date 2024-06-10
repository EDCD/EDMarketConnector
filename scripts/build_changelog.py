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
    with open("../CHANGELOG.md", encoding="utf-8") as changelog_file:
        content = changelog_file.read()
        changelog_list: list = content.split("---", maxsplit=2)
        changelog = changelog_list[2]
        changelog_list = changelog.split("===", maxsplit=2)
        changelog_list[0] = changelog_list[0].rstrip()
        changelog_list[0] = changelog_list[0].lstrip()
        changelog_list[0] += "\n==="
        changelog_list[1] = changelog_list[1].rstrip()
        changelog_list[1] = "\n".join(changelog_list[1].split("\n")[:-2])
        changelog = changelog_list[0] + changelog_list[1]
        changelog = changelog.rstrip()
        version = changelog.split("\n")[0]
        version = version.split(" ")[1]
        return changelog, version


def build_html(md_changelog) -> str:
    html_out = mistune.html(md_changelog)
    html_out = re.sub("h1", "h2", html_out)
    html_out += "\n<hr>"
    with open("script_output/html_changelog.txt", "w", encoding="utf-8") as html_file:
        html_file.write(html_out)
    return html_out


def build_fdev(
    vt_signed: str,
    vt_unsigned: str,
    version: str,
    gh_link: str,
    html: str,
) -> None:
    fdev_out = (
        "[HEADING=2][URL='"
        + gh_link
        + "'][SIZE=7]Release "
        + version
        + "[/SIZE][/URL][/HEADING]\n[URL='"
        + vt_signed
    )
    fdev_out += (
        "']Pre-emptive upload to VirusTotal[/URL]. ([URL='"
        + vt_unsigned
        + "']Unsigned Installer[/URL])\n\n"
    )

    if version.startswith("Pre-Release") or version.startswith("Beta"):
        fdev_out += f'This is a release candidate for {version}. It has been pushed to the "Beta" track for updates!'
        fdev_out += (
            '\n\nFor more information on the "Beta" update track, please read '
            "[URL='https://github.com/EDCD/EDMarketConnector/wiki/Participating-in-Open-Betas-of-EDMC']"
            "This Wiki Article[/URL]. Questions and comments are welcome!\n\n"
        )
    changelog_trim = html.split("\n", maxsplit=1)
    md_log = changelog_trim[1]
    md_log = re.sub("<p>", "", md_log)
    md_log = re.sub("</p>", "", md_log)
    md_log = re.sub("<strong>", "\n[HEADING=3]", md_log)
    md_log = re.sub("</strong>", "[/HEADING]", md_log)
    md_log = re.sub("<ul>", "[LIST]", md_log)
    md_log = re.sub("<li>", "[*]", md_log)
    md_log = re.sub("</li>", "", md_log)
    md_log = re.sub("<code>", "[ICODE]", md_log)
    md_log = re.sub("</code>", "[/ICODE]", md_log)
    md_log = re.sub("</ul>\n", "[/LIST]", md_log)
    fdev_out += md_log

    with open("script_output/fdev_changelog.txt", "w", encoding="utf-8") as fdev_file:
        fdev_file.write(fdev_out)
    return


def build_reddit(
    md_changelog: str, vt_signed: str, vt_unsigned: str, version: str, gh_link: str
) -> None:
    reddit_start = """# What Is Elite Dangerous Market Connector?

Elite Dangerous Market Connector ("EDMC") is a third-party application for use with Frontier Developments' game "Elite Dangerous". Its purpose is to facilitate supplying certain game data to, and in some cases retrieving it from, a number of websites and other tools.

To achieve this it utilizes the Journal Files written by the game when played on a PC. It also makes use of Frontier's Companion API  ("Frontier's CAPI"), accessible once you've authorized this application.

EDMC has a plugin system that many other developers have made use of to extend its functionality.

Find out more on the [EDMC Wiki](https://github.com/EDCD/EDMarketConnector/wiki).

~~----------------------------------------------------~~

You can also view the Elite: Dangerous Forum thread [HERE](https://forums.frontier.co.uk/threads/elite-dangerous-market-connector-edmc.618708/).

~~----------------------------------------------------~~

**As has become routine now, various anti-virus software are reporting a false positive on our installer and/or files it contains.  We've pre-emptively uploaded the installer to** [VirusTotal](
"""
    reddit_mid_1 = """) **if you want to check what it's saying.  Please see our** [Troubleshooting/AV-false-positives FAQ](https://github.com/EDCD/EDMarketConnector/wiki/Troubleshooting#installer-and-or-executables-flagged-as-malicious-viruses) **for further information.**

[Unsigned Installer]("""

    reddit_mid_2 = """) if you don't want to use the code-signed option.

~~----------------------------------------------------~~
"""
    versionsearch = f"Release {version}"
    updated = f"# [Release {version}]({gh_link})"
    md_changelog = re.sub("===\n", "", md_changelog)
    md_changelog = re.sub(versionsearch, updated, md_changelog)
    reddit_end = f"""

**Linux**

If you're running on Linux, try the [Flatpak](https://flathub.org/apps/io.edcd.EDMarketConnector) build of EDMC! (Update to {version} coming soon.)"""

    reddit_out = (
        reddit_start
        + vt_signed
        + reddit_mid_1
        + vt_unsigned
        + reddit_mid_2
        + md_changelog
        + reddit_end
    )
    with open(
        "script_output/reddit_changelog.txt", "w", encoding="utf-8"
    ) as reddit_file:
        reddit_file.write(reddit_out)


def main() -> None:
    md_changelog, version = get_changelog()
    print(f"Detected version {version} in the changelog. Continuing...")
    gh_link = input(f"Please enter the GitHub link for {version}: ")
    vt_signed = input("Please enter the VirusTotal URL for the Signed Installer: ")
    vt_unsigned = input("Please enter the VirusTotal URL for the Unsigned Installer: ")
    build_reddit(md_changelog, vt_signed, vt_unsigned, version, gh_link)
    html = build_html(md_changelog)
    build_fdev(vt_signed, vt_unsigned, version, gh_link, html)


if __name__ == "__main__":
    chdir(pathlib.Path(__file__).parent)
    main()
