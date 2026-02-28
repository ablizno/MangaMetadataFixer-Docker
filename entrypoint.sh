#!/bin/sh

if [ ! -f "$DATA_DIR/processed_files.db" ]; then
    echo "No database found. Running First Run Builder..."
    python "First Run - Builder.py"
fi

echo "Starting Manga Fixer Main..."
exec python "Manga Fixer Main.py"
