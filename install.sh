#!/usr/bin/env sh
# Backward-compatible Claude installer. Use tools/forge.py for other hosts.
#
#   ./install.sh            -> ./.claude/skills of the current directory
#   ./install.sh --global   -> ~/.claude/skills
#   ./install.sh <path>     -> <path>/.claude/skills
set -eu

FORGE_ROOT="$(cd "$(dirname "$0")" && pwd)"

case "${1:-}" in
  --global) exec python3 "$FORGE_ROOT/tools/forge.py" install --target claude --scope user --destination "$HOME" ;;
  "")       exec python3 "$FORGE_ROOT/tools/forge.py" install --target claude --destination "$(pwd)" ;;
  --*)      echo "Use python3 tools/forge.py --help for platform options" >&2; exit 2 ;;
  *)        exec python3 "$FORGE_ROOT/tools/forge.py" install --target claude --destination "$1" ;;
esac
