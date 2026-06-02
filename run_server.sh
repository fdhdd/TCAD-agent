#!/bin/bash
# Edit STROOT and STRELEASE below to match your TCAD installation.
cd "$(dirname "$0")" || exit 1
export PATH="$HOME/.local/bin:$PATH"
export STROOT=/usr/synopsys/sentaurus/X-2025.06
export STRELEASE=X-2025.06
export LD_LIBRARY_PATH="${STROOT}/tcad/${STRELEASE}/linux64/lib"
exec "${STROOT}/tcad/${STRELEASE}/linux64/bin/python3.11" \
  -c "
import os, sys
os.environ['PATH'] = os.path.expanduser('~/.local/bin') + ':' + os.environ.get('PATH', '')
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# Start embedded simulation progress monitor server (port 2025)
import sim_progress
sim_progress.start_monitor_server(port=2025)

from langgraph_cli.cli import cli
cli(['dev', '--host', '0.0.0.0', '--port', '2024'], standalone_mode=False)
"
