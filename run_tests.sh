#!/usr/bin/env bash
set -e

echo "=== Running IncuBrix Prompt-Based Video Editing Engine Test Suite ==="
python -m pytest tests/ -v
echo "=== All Tests Passed Successfully! ==="
