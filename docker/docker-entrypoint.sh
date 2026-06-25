#!/bin/bash
set -e

if [ "$1" = 'app-server' ]; then
    echo "Starting CBGM app-server; the browse URL is printed below once ready."
    exec python3 -m server -vvv
fi

if [ "$1" = 'cbgm' ]; then
    echo "*************************"
    echo "* Running the CBGM ...  *"
    echo "*************************"
    exec python3 -m scripts.cbgm -vvv instance/acts_ph4.conf
fi
