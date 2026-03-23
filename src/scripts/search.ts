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

let activeTopics = new Set<string>();
let currentSearch = '';
let currentSort = 'newest';

function getFilteredSlugs(): string[] {
  let pool = episodes;

  if (currentSearch) {
    pool = fuse.search(currentSearch).map((r) => r.item);
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
  });

  visibleSlugs.forEach((slug, i) => {
    const card = cardMap.get(slug);
    if (card) card.style.order = String(i);
  });

  const total = episodes.length;
  const shown = visibleSlugs.length;
  if (currentSearch || activeTopics.size > 0) {
    searchCount.textContent = `Showing ${shown} of ${total} episodes`;
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
  debounceTimer = setTimeout(() => {
    currentSearch = searchInput.value.trim();
    render();
  }, 200);
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

  render();
}

restoreFromHash();
