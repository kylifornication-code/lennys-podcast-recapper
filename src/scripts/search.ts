import Fuse from 'fuse.js';

interface Episode {
  slug: string;
  guest: string;
  title: string;
  video_id: string;
  publish_date: string;
  description: string;
  duration: string;
  duration_seconds: number;
  view_count: number;
  keywords: string[];
}

const dataEl = document.getElementById('episodes-data');
const episodes: Episode[] = dataEl ? JSON.parse(dataEl.textContent || '[]') : [];

const fuse = new Fuse(episodes, {
  keys: [
    { name: 'title', weight: 0.35 },
    { name: 'guest', weight: 0.3 },
    { name: 'keywords', weight: 0.2 },
    { name: 'description', weight: 0.15 },
  ],
  threshold: 0.35,
  ignoreLocation: true,
});

const searchInput = document.getElementById('search-input') as HTMLInputElement;
const searchCount = document.getElementById('search-count')!;
const cardGrid = document.getElementById('card-grid')!;
const noResults = document.getElementById('no-results')!;
const sortSelect = document.getElementById('sort-select') as HTMLSelectElement;
const topicsToggle = document.getElementById('topics-toggle');
const topicsExpanded = document.getElementById('filter-topics-expanded');

const allCards = Array.from(cardGrid.querySelectorAll('.card')) as HTMLElement[];
const cardMap = new Map<string, HTMLElement>();
allCards.forEach((card) => {
  const slug = card.getAttribute('data-slug');
  if (slug) cardMap.set(slug, card);
});

const episodeMap = new Map<string, Episode>();
episodes.forEach((ep) => episodeMap.set(ep.slug, ep));

let activeTopics = new Set<string>();
let currentSearch = '';
let currentSort = 'newest';
let pagefindSlugs = new Set<string>();
let pagefindExcerpts = new Map<string, string>();
let pagefindReady = false;
let pagefindInstance: any = null;

async function initPagefind() {
  if ((window as any).__pagefind) {
    pagefindInstance = (window as any).__pagefind;
    pagefindReady = true;
    return;
  }
  for (let i = 0; i < 200; i++) {
    await new Promise((r) => setTimeout(r, 100));
    if ((window as any).__pagefind) {
      pagefindInstance = (window as any).__pagefind;
      pagefindReady = true;
      return;
    }
  }
}
initPagefind();

async function searchTranscripts(query: string): Promise<void> {
  pagefindSlugs.clear();
  pagefindExcerpts.clear();

  if (!pagefindReady || !pagefindInstance || !query) return;

  try {
    const search = await Promise.race([
      pagefindInstance.search(query),
      new Promise<never>((_, reject) => setTimeout(() => reject('timeout'), 30000)),
    ]);
    const top = search.results.slice(0, 50);
    const loaded = await Promise.all(top.map((r: any) => r.data()));

    for (const hit of loaded) {
      const slug = hit.meta?.slug;
      if (slug && cardMap.has(slug)) {
        pagefindSlugs.add(slug);
        if (hit.excerpt) {
          pagefindExcerpts.set(slug, hit.excerpt);
        }
      }
    }
  } catch {
    // Pagefind unavailable or timeout
  }
}

function getFilteredSlugs(): string[] {
  let pool = episodes;

  if (currentSearch) {
    const fuseResults = fuse.search(currentSearch).map((r) => r.item);
    const fuseSlugs = new Set(fuseResults.map((ep) => ep.slug));

    for (const slug of pagefindSlugs) {
      if (!fuseSlugs.has(slug)) {
        const ep = episodeMap.get(slug);
        if (ep) fuseResults.push(ep);
      }
    }
    pool = fuseResults;
  }

  if (activeTopics.size > 0) {
    pool = pool.filter((ep) =>
      [...activeTopics].every((t) => ep.keywords.includes(t))
    );
  }

  pool = sortEpisodes(pool, currentSort);
  return pool.map((ep) => ep.slug);
}

function sortEpisodes(eps: Episode[], sort: string): Episode[] {
  const sorted = [...eps];
  switch (sort) {
    case 'oldest':
      sorted.sort((a, b) => (a.publish_date || '').localeCompare(b.publish_date || ''));
      break;
    case 'views':
      sorted.sort((a, b) => (b.view_count || 0) - (a.view_count || 0));
      break;
    case 'longest':
      sorted.sort((a, b) => (b.duration_seconds || 0) - (a.duration_seconds || 0));
      break;
    default:
      sorted.sort((a, b) => (b.publish_date || '').localeCompare(a.publish_date || ''));
  }
  return sorted;
}

function render() {
  const visibleSlugs = getFilteredSlugs();
  const visibleSet = new Set(visibleSlugs);

  allCards.forEach((card) => {
    const slug = card.getAttribute('data-slug')!;
    card.style.display = visibleSet.has(slug) ? '' : 'none';

    const excerptEl = card.querySelector('.card-excerpt') as HTMLElement | null;
    if (excerptEl) {
      const excerpt = pagefindExcerpts.get(slug);
      if (excerpt && visibleSet.has(slug) && currentSearch) {
        excerptEl.innerHTML = excerpt;
        excerptEl.style.display = '';
      } else {
        excerptEl.innerHTML = '';
        excerptEl.style.display = 'none';
      }
    }
  });

  visibleSlugs.forEach((slug, i) => {
    const card = cardMap.get(slug);
    if (card) card.style.order = String(i);
  });

  const total = episodes.length;
  const shown = visibleSlugs.length;
  if (currentSearch || activeTopics.size > 0) {
    const transcriptNote = currentSearch && pagefindSlugs.size > 0
      ? ` (includes transcript matches)`
      : '';
    searchCount.textContent = `Showing ${shown} of ${total} episodes${transcriptNote}`;
  } else {
    searchCount.textContent = '';
  }

  noResults.style.display = shown === 0 ? '' : 'none';
  cardGrid.style.display = shown === 0 ? 'none' : '';

  updateHash();
}

let debounceTimer: ReturnType<typeof setTimeout>;
searchInput.addEventListener('input', () => {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(async () => {
    currentSearch = searchInput.value.trim();
    render();

    if (currentSearch && pagefindReady) {
      await searchTranscripts(currentSearch);
      render();
    } else {
      pagefindSlugs.clear();
      pagefindExcerpts.clear();
    }
  }, 250);
});

sortSelect.addEventListener('change', () => {
  currentSort = sortSelect.value;
  render();
});

document.addEventListener('click', (e) => {
  const pill = (e.target as HTMLElement).closest('.topic-pill') as HTMLElement | null;
  if (!pill) return;
  const topic = pill.getAttribute('data-topic');
  if (!topic) return;

  if (activeTopics.has(topic)) {
    activeTopics.delete(topic);
    pill.classList.remove('active');
  } else {
    activeTopics.add(topic);
    pill.classList.add('active');
  }
  render();
});

if (topicsToggle && topicsExpanded) {
  topicsToggle.addEventListener('click', () => {
    const shown = topicsExpanded.style.display !== 'none';
    topicsExpanded.style.display = shown ? 'none' : 'flex';
    topicsToggle.textContent = shown
      ? `+${topicsExpanded.querySelectorAll('.topic-pill').length} more`
      : 'Show fewer';
  });
}

function updateHash() {
  const params = new URLSearchParams();
  if (currentSearch) params.set('q', currentSearch);
  if (activeTopics.size > 0) params.set('topics', [...activeTopics].join(','));
  if (currentSort !== 'newest') params.set('sort', currentSort);
  const hash = params.toString();
  history.replaceState(null, '', hash ? `#${hash}` : window.location.pathname);
}

function restoreFromHash() {
  const hash = window.location.hash.slice(1);
  if (!hash) return;
  const params = new URLSearchParams(hash);

  const q = params.get('q');
  if (q) {
    currentSearch = q;
    searchInput.value = q;
  }

  const topics = params.get('topics');
  if (topics) {
    topics.split(',').forEach((t) => {
      activeTopics.add(t);
      document.querySelectorAll(`.topic-pill[data-topic="${t}"]`).forEach((el) =>
        el.classList.add('active')
      );
    });
  }

  const sort = params.get('sort');
  if (sort) {
    currentSort = sort;
    sortSelect.value = sort;
  }

  (async () => {
    if (currentSearch && pagefindReady) {
      await searchTranscripts(currentSearch);
    }
    render();
  })();
}

restoreFromHash();
