import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const episodes = defineCollection({
  loader: glob({
    pattern: '*/transcript.md',
    base: './data/episodes',
    generateId: ({ entry }) => entry.split('/')[0],
  }),
  schema: z.object({
    guest: z.string().default(''),
    title: z.string().default(''),
    video_id: z.string().default(''),
    youtube_url: z.string().default(''),
    publish_date: z.preprocess(
      (val) => {
        if (val instanceof Date) return val.toISOString().split('T')[0];
        if (typeof val === 'string') return val;
        return '';
      },
      z.string().default(''),
    ),
    description: z.string().default(''),
    duration_seconds: z.number().default(0),
    duration: z.string().default(''),
    view_count: z.number().default(0),
    channel: z.string().default("Lenny's Podcast"),
    keywords: z.array(z.string()).default([]),
  }),
});

export const collections = { episodes };
