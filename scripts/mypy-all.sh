#!/usr/bin/env bash
#

mypy $(git ls-tree --full-tree -r --name-only HEAD | grep -E '\.py$')
