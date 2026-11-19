#!/usr/bin/env bash
# Run an xy-jianying script with the skill's own Python (.venv made by install.sh).
#   bash run.sh doctor.py --full
#   bash run.sh live_run.py job.json
DIR="$(cd "$(dirname "$0")" && pwd)"
PY="$DIR/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"
S="$1"; shift
case "$S" in */*) [ -f "$S" ] || S="$DIR/scripts/$S" ;; *) S="$DIR/scripts/$S" ;; esac
exec "$PY" -X utf8 "$S" "$@"
