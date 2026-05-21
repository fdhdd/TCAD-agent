#!/bin/bash
# TCAD Agent launch script
# Uses TCAD's bundled Python 3.11 for swbpy2 compatibility

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export STROOT=/usr/synopsys/sentaurus/X-2025.06
export STRELEASE=X-2025.06
export LD_LIBRARY_PATH="$STROOT/tcad/$STRELEASE/linux64/lib:$LD_LIBRARY_PATH"

cd "$SCRIPT_DIR"
source .venv/bin/activate
exec python agent.py "$@"
