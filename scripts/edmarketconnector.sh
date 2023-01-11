#!/bin/sh

set -e

# NB: EDMC_PATH is replaced with the correct value by the
#     scripts/linux-setup.sh script. So, no, there's no missing '$' here.
cd EDMC_PATH
python3 EDMarketConnector.py
