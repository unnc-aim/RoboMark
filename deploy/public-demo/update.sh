#!/usr/bin/env bash
set -euo pipefail
target_host="${1:-jproot}"
# Source, dependencies and frontend builds are now managed entirely on the server.
ssh -o ClearAllForwardings=yes "$target_host" 'bash "$HOME/robomark/app/deploy/public-demo/update-server.sh"'
