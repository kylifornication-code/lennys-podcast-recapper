# Lenny's Podcast Recapper

**Every conversation. One place to explore.**

Lenny's Podcast Recapper is a fast, searchable home for hundreds of [Lenny's Podcast](https://www.youtube.com/@LennysPodcast) episodes—the interviews with product leaders, growth experts, and operators that people return to for years. Stop hunting through YouTube and spreadsheets. Find the episode, the guest, or the exact moment in a transcript you care about.

---

## Why this exists

Lenny's guests share concrete, tactical advice on building and scaling products. Those insights live in long-form conversations. This project turns that archive into something you can **browse**, **filter**, and **search**—so you can go from “I remember someone talking about onboarding…” to the right episode in seconds.

---

## What you can do

- **Browse a living catalog** — Episodes with guests, titles, dates, and runtimes, sorted the way you expect.
- **Search the way humans search** — Fuzzy search across guests, titles, descriptions, and AI-tagged topics. When you build the site for production, search extends into **full transcript text**, so keyword-level discovery works too.
- **Filter by topic** — Explore themes like product management, leadership, and growth through tagged episodes.
- **Read on the page, watch on YouTube** — Each episode opens to a clean transcript view with a direct link to the official video—so Lenny and guests stay the source of truth.

---

## Try it

**Live site:** [kylejames.github.io/Lennys-podcast-recapper](https://kylejames.github.io/Lennys-podcast-recapper/)

Run it locally:

```bash
npm install && npm run dev
```

Production build (includes full-text index for transcript search):

```bash
npm run build && npm run preview
```

---

## What’s under the hood (short version)

The site is built with [Astro](https://astro.build/). Episode content lives in this repo as structured transcripts and metadata; a daily automation pipeline keeps raw transcripts in sync and enriches new episodes from YouTube. Topic tags help you discover episodes by theme.

If you’re extending scripts, workflows, or data layouts, see **[CLAUDE.md](CLAUDE.md)** for repository conventions and tooling.

---

## Disclaimer

This project is for **education and research**. All show content belongs to Lenny's Podcast and the respective guests. Watch, subscribe, and support the show on the [official YouTube channel](https://www.youtube.com/@LennysPodcast).
