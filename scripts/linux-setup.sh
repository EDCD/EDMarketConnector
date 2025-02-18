#!/usr/bin/env bash
#
# Set up necessary support files to make running EDMarketConnect streamlined
# on Linux.
#

###########################################################################
# Shell script launcher
#
#  This needs to be in an appropriate component of $PATH so that the
# reference in the .desktop file will work.
###########################################################################
#######################################################
# Determine where edmarketconnector.sh needs to go
#######################################################
# Really we need this to be "${HOME}/.local/bin", so check that is in $PATH
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]];
then
        echo "You need to have '${HOME}/.local/bin' in your PATH"
        echo "Please fix this (might require relogging) and try again"
        exit 1
fi
EDMC_BIN_PATH="${HOME}/.local/bin"
if [ ! -d "${EDMC_BIN_PATH}" ];
then
        echo "'${EDMC_BIN_PATH}' must exist and be a directory!"
        exit 2
fi
#######################################################

#######################################################
# Determine where the source is located
#######################################################
# We know where this script is situated within an unzip/git clone of
# the source code, so set EDMC_PATH based on that.
# This is in `scripts/` of the source, so one directory up
EDMC_PATH="$(dirname $0)/.."
# And we need the *full* absolute path
EDMC_PATH="$(realpath ${EDMC_PATH})"
echo "EDMC_PATH = ${EDMC_PATH}"
#######################################################


#######################################################
# Copy an edited version of edmarketconnector.sh into place
#######################################################
echo "Copying launcher shell script into place..."
sed -e "s#EDMC_PATH#${EDMC_PATH}#g;" \
        < "${EDMC_PATH}/scripts/edmarketconnector.sh" \
        > "${EDMC_BIN_PATH}/edmarketconnector"
#######################################################
###########################################################################

###########################################################################
# Desktop file
#
#  This needs to be in a path where any XDG-compliant environment will be
# able to find it.
###########################################################################
echo "Copying .desktop file into place ..."
install -d -m700 "${HOME}/.local/share/applications"
install -t "${HOME}/.local/share/applications" "${EDMC_PATH}/io.edcd.EDMarketConnector.desktop"
###########################################################################

###########################################################################
# Icon file
#
#  This needs to be in a path where any XDG-compliant environment will be
# able to find it.
###########################################################################
echo "Copying icon file into place..."
install -d -m700 "${HOME}/.local/share/icons/hicolor/512x512/apps"
install -t "${HOME}/.local/share/icons/hicolor/512x512/apps" "${EDMC_PATH}/io.edcd.EDMarketConnector.png"
###########################################################################
