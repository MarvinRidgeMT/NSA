#!/bin/zsh
set -e
cd "$(dirname "$0")"
echo "POLARIS X — 5D Lunar Digital Twin"
echo "Local app: http://localhost:5173"
open http://localhost:5173
python3 -m http.server 5173
