"""
installer.py - Build the Installer.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.
"""
import os
import subprocess
from string import Template
from build import build
from config import _static_appversion as appversion


def iss_build(template_path: str, output_file: str) -> None:
    """Build the .iss file needed for building the installer EXE."""
    sub_vals = {"appver": appversion}
    with open(template_path, encoding="UTF8") as template_file:
        src = Template(template_file.read())
        newfile = src.substitute(sub_vals)
    with open(output_file, "w", encoding="UTF8") as new_file:
        new_file.write(newfile)


def run_inno_setup_installer(iss_path: str) -> None:
    """Run the Inno installer, building the installation exe."""
    # Get the path to the Inno Setup compiler (iscc.exe) (Currently set to default path)
    inno_setup_compiler_path: str = "C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe"

    # Check if the Inno Setup compiler executable exists
    if not os.path.isfile(inno_setup_compiler_path):
        print(f"Error: Inno Setup compiler not found at '{inno_setup_compiler_path}'.")
        return

    # Check if the provided .iss file exists
    if not os.path.isfile(iss_file_path):
        print(f"Error: The provided .iss file '{iss_path}' not found.")
        return

    # Run the Inno Setup compiler with the provided .iss file
    try:
        subprocess.run([inno_setup_compiler_path, iss_file_path], check=True)
    except subprocess.CalledProcessError as err:
        print(
            f"Error: Inno Setup compiler returned an error (exit code {err.returncode}):"
        )
        print(err.output.decode())
    except Exception as err:
        print(f"Error: An unexpected error occurred: {err}")


if __name__ == "__main__":
    build()
    # Add the ISS Template File
    iss_template_path: str = "./resources/EDMC_Installer_Config_template.txt"
    iss_file_path: str = "./EDMC_Installer_Config.iss"
    # Build the ISS file
    iss_build(iss_template_path, iss_file_path)
    run_inno_setup_installer(iss_file_path)
