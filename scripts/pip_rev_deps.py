"""Search for dependencies given a package."""
import sys

import pkg_resources


def find_reverse_deps(package_name: str) -> list[str]:
    """
    Find the packages that depend on the named one.

    :param package_name: Target package.
    :return: List of packages that depend on this one.
    """
    return [
        pkg.project_name for pkg in pkg_resources.WorkingSet()
        if package_name in {req.project_name for req in pkg.requires()}
    ]


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python reverse_deps.py <package_name>")
        sys.exit(1)

    package_name = sys.argv[1]
    reverse_deps = find_reverse_deps(package_name)

    if reverse_deps:
        print(f"Reverse dependencies of '{package_name}':")
        for dep in reverse_deps:
            print(dep)
    else:
        print(f"No reverse dependencies found for '{package_name}'.")
