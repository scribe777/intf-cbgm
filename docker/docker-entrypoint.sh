#!/bin/bash
set -e

if [ "$1" = 'app-server' ]; then
    echo "Starting CBGM app-server; the browse URL is printed below once ready."
    # Optional warm JVM co-process for AI local-stemma proposals. It binds
    # localhost only and reads its engine API keys from this container's
    # environment (ANTHROPIC_API_KEY, GEMINI_API_KEY, ...). Off unless enabled.
    if [ -n "$AI_LOCALSTEMMA_ENABLED" ]; then
        echo "Starting local-stemma AI server on 127.0.0.1:8078"
        java -cp '/home/ntg/ai/*' org.crosswire.community.ai.cbgm.LocalStemmaServer \
             --port 8078 >> /tmp/localstemma.log 2>&1 &
    fi
    exec python3 -m server -vvv
fi

if [ "$1" = 'cbgm' ]; then
    echo "*************************"
    echo "* Running the CBGM ...  *"
    echo "*************************"
    exec python3 -m scripts.cbgm -vvv instance/acts_ph4.conf
fi
