#!/bin/bash

# Download latest transcripts from the public Dropbox shared folder
# Usage: ./scripts/sync-dropbox.sh
#
# Downloads the shared folder as a zip, extracts .txt files,
# and copies any new ones into data/raw-transcripts/

set -e

RAW_DIR="${RAW_DIR:-data/raw-transcripts}"
DROPBOX_URL="${DROPBOX_URL:-https://www.dropbox.com/scl/fo/yxi4s2w998p1gvtpu4193/AMdNPR8AOw0lMklwtnC0TrQ?rlkey=j06x0nipoti519e0xgm23zsn9&dl=1}"

TEMP_DIR=$(mktemp -d)
ZIP_FILE="$TEMP_DIR/transcripts.zip"
EXTRACT_DIR="$TEMP_DIR/extracted"

trap 'rm -rf "$TEMP_DIR"' EXIT

echo "Downloading transcripts from Dropbox..."
curl -L -o "$ZIP_FILE" "$DROPBOX_URL" 2>/dev/null

if [[ ! -s "$ZIP_FILE" ]]; then
    echo "Error: Download failed or file is empty"
    exit 1
fi

echo "Extracting archive..."
mkdir -p "$EXTRACT_DIR"
unzip -q -o "$ZIP_FILE" -d "$EXTRACT_DIR"

# Find all .txt files (may be nested in a subdirectory)
mkdir -p "$RAW_DIR"

NEW_COUNT=0
TOTAL=0

find "$EXTRACT_DIR" -name "*.txt" -type f | while read -r src_file; do
    filename=$(basename "$src_file")
    dest="$RAW_DIR/$filename"
    ((TOTAL++)) || true

    if [[ ! -f "$dest" ]]; then
        cp "$src_file" "$dest"
        echo "  New: $filename"
        ((NEW_COUNT++)) || true
    fi
done

echo ""
echo "Sync complete. New transcripts added: $NEW_COUNT"
