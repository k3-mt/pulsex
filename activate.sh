#!/bin/bash
# Manual activation script for the virtual environment
# Usage: source activate.sh

if [ -f ".venv/bin/activate" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
    echo "Virtual environment activated!"
    echo "Python path: $(which python)"
    echo "Pip path: $(which pip)"
else
    echo "Virtual environment not found. Run 'make install' first."
    exit 1
fi
