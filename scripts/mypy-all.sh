#!/usr/bin/env bash
#
# Run mypy checks against all the relevant files

# We assume that all `.py` files in git should be checked, and *only* those.
mypy $@ $(git ls-tree --full-tree -r --name-only HEAD | grep -E '\.py$')
