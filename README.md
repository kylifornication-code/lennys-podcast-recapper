# Lenny's Podcast Recapper

A consolidated repository for working with [Lenny's Podcast](https://www.youtube.com/@LennysPodcast) transcripts. Contains 300+ episode transcripts in two formats, an AI-generated topic index, and tooling for building podcast recap applications.

## Repository Structure

```
├── data/
│   ├── episodes/            # 303 structured transcripts (markdown + YAML metadata)
│   │   └── {guest-name}/
│   │       └── transcript.md
│   ├── raw-transcripts/     # 311 raw transcripts (plain text, from Dropbox archive)
│   │   └── {Guest Name}.txt
│   └── index/               # AI-generated topic index (89 topic files)
│       ├── README.md
│       └── {topic}.md
├── scripts/
│   └── build-index.sh       # Regenerate the topic index
├── CLAUDE.md                # AI assistant guidance
└── README.md
```

## Data Sources

### Structured Transcripts (`data/episodes/`)

303 episodes as markdown files with rich YAML frontmatter:

- `guest` - Name of the guest(s)
- `title` - Full episode title
- `youtube_url` - Link to the YouTube video
- `video_id` - YouTube video ID
- `publish_date` - Publication date (YYYY-MM-DD)
- `description` - Episode description
- `duration_seconds` / `duration` - Episode length
- `view_count` - Views at time of archival
- `keywords` - AI-generated topic tags

### Raw Transcripts (`data/raw-transcripts/`)

311 plain text files with speaker-timestamped dialogue. These cover 8 additional episodes not in the structured set.

### Topic Index (`data/index/`)

89 AI-generated topic files grouping episodes by keyword (e.g., product management, leadership, growth strategy). Browse the full list at [data/index/README.md](data/index/README.md).

## Quick Start

**Browse by topic:**

```bash
cat data/index/README.md
```

**Search transcripts:**

```bash
grep -r "product-market fit" data/episodes/
```

**Rebuild the topic index:**

```bash
./scripts/build-index.sh
```

## About Lenny's Podcast

Lenny's Podcast features interviews with world-class product leaders and growth experts, providing concrete, actionable, and tactical advice to help you build, launch, and grow your own product.

## Disclaimer

This archive is for educational and research purposes. All content belongs to Lenny's Podcast and the respective guests. Please visit the [official YouTube channel](https://www.youtube.com/@LennysPodcast) to support the creators.
