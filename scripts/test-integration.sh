#!/usr/bin/env bash
set -euo pipefail

python3 -m pytest scripts/test-execucao.py scripts/test-raciocinio.py scripts/test-resiliencia.py "$@"
