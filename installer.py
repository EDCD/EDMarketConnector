"""
installer.py - Build the Installer.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.
"""
import os
import subprocess
from build import build


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
    # Replace 'your_iss_file.iss' with the path to your actual .iss file
    iss_file_path: str = "./EDMC_Installer_Config.iss"
    run_inno_setup_installer(iss_file_path)
