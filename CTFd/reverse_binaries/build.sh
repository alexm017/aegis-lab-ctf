#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$BASE_DIR/src"
OUT_DIR="$BASE_DIR/bin"

mkdir -p "$OUT_DIR"

gcc -O2 -s -fno-stack-protector -no-pie "$SRC_DIR/license_check.c" -o "$OUT_DIR/license_check"
gcc -O2 -s -fno-stack-protector -no-pie "$SRC_DIR/xor_strings.c" -o "$OUT_DIR/xor_strings"
gcc -O2 -s -fno-stack-protector -no-pie "$SRC_DIR/jump_maze.c" -o "$OUT_DIR/jump_maze"
gcc -O2 -s -fno-stack-protector -no-pie "$SRC_DIR/patch_me.c" -o "$OUT_DIR/patch_me"

echo "Built binaries:"
ls -l "$OUT_DIR"

