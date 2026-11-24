#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Run in the foreground; Ctrl-C stops the in-memory ledger.
python3 scripts/prepare.py
exec daml sandbox --port 17601 --admin-api-port 17602 \
  --sequencer-public-port 17603 --sequencer-admin-port 17604 \
  --mediator-admin-port 17605 --json-api-port 17606 \
  --config .runtime/auth.conf
