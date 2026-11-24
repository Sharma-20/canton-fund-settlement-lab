#!/usr/bin/env python3
"""Create or validate the owner-only, loopback-only synthetic lab configuration."""
import pathlib
import sys
from local_config import prepare

try:
    prepare(pathlib.Path(__file__).resolve().parents[1])
except (ValueError, OSError):
    sys.exit('Configuration rejected. Require owner-only .runtime (0700), regular auth.conf (0600), and the generated loopback-only template. No configuration contents were printed or overwritten.')
print('Local synthetic-lab authentication configuration validated; no credentials printed.')
