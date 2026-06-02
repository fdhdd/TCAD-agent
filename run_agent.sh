#!/bin/bash
# TCAD Agent launch script
# Uses TCAD's bundled Python 3.11 for swbpy2 compatibility.
# Edit STROOT and STRELEASE below to match your TCAD installation.

export STROOT=/usr/synopsys/sentaurus/X-2025.06
export STRELEASE=X-2025.06

export LD_LIBRARY_PATH="${STROOT}/tcad/${STRELEASE}/linux64/lib:${LD_LIBRARY_PATH}"
TCAD_PYTHON="${STROOT}/tcad/${STRELEASE}/linux64/bin/python3.11"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$SCRIPT_DIR"
exec "$TCAD_PYTHON" agent.py "$@"
