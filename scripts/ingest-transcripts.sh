#!/bin/bash

# Convert raw .txt transcripts into structured episodes
# Usage: ./scripts/ingest-transcripts.sh
#
# For each .txt file in data/raw-transcripts/ that doesn't yet have a
# corresponding episode in data/episodes/, creates a new episode directory
# with a transcript.md file containing YAML frontmatter and the transcript.
#
# Idempotent: skips episodes that already exist.

set -e

RAW_DIR="${RAW_DIR:-data/raw-transcripts}"
EPISODES_DIR="${EPISODES_DIR:-data/episodes}"

if [[ ! -d "$RAW_DIR" ]]; then
    echo "Error: $RAW_DIR not found"
    exit 1
fi

mkdir -p "$EPISODES_DIR"

TOTAL=0
NEW=0
SKIPPED=0

for txt_file in "$RAW_DIR"/*.txt; do
    [[ -f "$txt_file" ]] || continue
    ((TOTAL++)) || true

    basename_no_ext=$(basename "$txt_file" .txt)

    # Generate slug: lowercase, spaces/+ to hyphens, strip special chars except hyphens and underscores
    slug=$(echo "$basename_no_ext" \
        | tr '[:upper:]' '[:lower:]' \
        | tr ' +' '-' \
        | tr -d '.' \
        | tr -cd 'a-z0-9_-' \
        | sed 's/--*/-/g')

    episode_dir="$EPISODES_DIR/$slug"

    if [[ -d "$episode_dir" ]]; then
        ((SKIPPED++)) || true
        continue
    fi

    echo "Creating episode: $slug (from $basename_no_ext)"

    # Extract guest name from first speaker line (format: "Name (HH:MM:SS):")
    guest="$basename_no_ext"
    first_speaker=$(head -1 "$txt_file" | sed -n 's/\(.*\) ([0-9][0-9]:[0-9][0-9]:[0-9][0-9]).*/\1/p' | sed 's/[[:space:]]*$//' || true)
    if [[ -n "$first_speaker" && "$first_speaker" != "Lenny" && "$first_speaker" != "Lenny Rachitsky" ]]; then
        guest="$first_speaker"
    fi

    mkdir -p "$episode_dir"

    # Write structured transcript.md with YAML frontmatter
    cat > "$episode_dir/transcript.md" << FRONTMATTER
---
guest: "$guest"
title: ""
youtube_url: ""
video_id: ""
publish_date: ""
description: ""
duration_seconds: 0
duration: ""
view_count: 0
channel: Lenny's Podcast
keywords: []
---

FRONTMATTER

    cat "$txt_file" >> "$episode_dir/transcript.md"

    ((NEW++)) || true
done

echo ""
echo "Ingestion complete."
echo "  Total raw transcripts: $TOTAL"
echo "  New episodes created:  $NEW"
echo "  Already existed:       $SKIPPED"
