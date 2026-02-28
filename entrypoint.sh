#!/bin/sh

if [ ! -f "$DATA_DIR/processed_files.db" ]; then
    echo "No database found. Running First Run Builder..."
    python first_run_builder.py
fi

echo "Starting Manga Fixer Main..."
exec python manga_fixer_main.py
