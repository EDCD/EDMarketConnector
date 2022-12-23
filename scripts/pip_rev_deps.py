#!/usr/bin/env python
"""Find the reverse dependencies of a package according to pip."""
import sys

import pkg_resources


def find_reverse_deps(package_name: str):
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
    print(find_reverse_deps(sys.argv[1]))
