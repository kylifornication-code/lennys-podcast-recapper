import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://kylejames.github.io',
  base: '/Lennys-podcast-recapper',
  build: {
    format: 'directory',
  },
});
