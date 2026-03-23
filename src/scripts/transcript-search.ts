const MARK = 'episode-inline-search-hit';
const MARK_ACTIVE = 'episode-inline-search-hit--active';

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function clearHighlights(roots: HTMLElement[]): void {
  for (const root of roots) {
    const marks = [...root.querySelectorAll(`mark.${MARK}`)];
    for (const mark of marks) {
      const parent = mark.parentNode;
      if (!parent) continue;
      while (mark.firstChild) parent.insertBefore(mark.firstChild, mark);
      parent.removeChild(mark);
    }
    root.normalize();
  }
}

function highlightTextNode(textNode: Text, re: RegExp): void {
  const text = textNode.textContent || '';
  const parent = textNode.parentNode;
  if (!parent) return;

  const frag = document.createDocumentFragment();
  let lastIndex = 0;
  const flags = re.flags.includes('g') ? re.flags : `${re.flags}g`;
  const copy = new RegExp(re.source, flags);
  let m: RegExpExecArray | null;
  let found = false;

  while ((m = copy.exec(text)) !== null) {
    found = true;
    if (m.index > lastIndex) {
      frag.appendChild(document.createTextNode(text.slice(lastIndex, m.index)));
    }
    const mark = document.createElement('mark');
    mark.className = MARK;
    mark.textContent = m[0];
    frag.appendChild(mark);
    lastIndex = m.index + m[0].length;
    if (m[0].length === 0) copy.lastIndex++;
  }

  if (!found) return;
  if (lastIndex < text.length) {
    frag.appendChild(document.createTextNode(text.slice(lastIndex)));
  }
  parent.replaceChild(frag, textNode);
}

function collectTextNodes(root: HTMLElement): Text[] {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      let p: Node | null = node.parentNode;
      while (p) {
        if (p instanceof Element) {
          const tag = p.tagName;
          if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'NOSCRIPT') {
            return NodeFilter.FILTER_REJECT;
          }
        }
        p = p.parentNode;
      }
      return NodeFilter.FILTER_ACCEPT;
    },
  });
  const out: Text[] = [];
  let n: Node | null;
  while ((n = walker.nextNode())) {
    out.push(n as Text);
  }
  return out;
}

function highlightInRoot(root: HTMLElement, query: string): void {
  const q = query.trim();
  if (!q || q.length > 500) return;
  const escaped = escapeRegExp(q);
  const re = new RegExp(escaped, 'gi');
  const textNodes = collectTextNodes(root);
  for (const textNode of textNodes) {
    if (!textNode.parentNode) continue;
    const text = textNode.textContent || '';
    if (!new RegExp(escaped, 'i').test(text)) continue;
    highlightTextNode(textNode, re);
  }
}

function getRoots(): HTMLElement[] {
  return [
    document.querySelector('.transcript-content'),
    document.querySelector('.episode-description-text'),
  ].filter((el): el is HTMLElement => el !== null);
}

const input = document.getElementById('episode-transcript-search-input') as HTMLInputElement | null;
const countEl = document.getElementById('episode-transcript-search-count');
const prevBtn = document.getElementById('episode-transcript-search-prev') as HTMLButtonElement | null;
const nextBtn = document.getElementById('episode-transcript-search-next') as HTMLButtonElement | null;

if (input && countEl && prevBtn && nextBtn) {
  let currentIndex = 0;
  let debounceTimer: ReturnType<typeof setTimeout>;

  function allMarks(): HTMLElement[] {
    const roots = getRoots();
    const list: HTMLElement[] = [];
    for (const root of roots) {
      list.push(...root.querySelectorAll<HTMLElement>(`mark.${MARK}`));
    }
    return list;
  }

  function setActive(index: number): void {
    const marks = allMarks();
    marks.forEach((el) => el.classList.remove(MARK_ACTIVE));
    if (marks.length === 0) return;
    const i = ((index % marks.length) + marks.length) % marks.length;
    currentIndex = i;
    const active = marks[i];
    active.classList.add(MARK_ACTIVE);
    active.scrollIntoView({ block: 'center', behavior: 'smooth' });
  }

  function updateUI(): void {
    const marks = allMarks();
    const n = marks.length;
    const q = input.value.trim();

    if (!q) {
      countEl.textContent = '';
      prevBtn.disabled = true;
      nextBtn.disabled = true;
      return;
    }

    countEl.textContent = n === 0 ? 'No matches' : `${currentIndex + 1} / ${n}`;
    prevBtn.disabled = n === 0;
    nextBtn.disabled = n === 0;
  }

  function runSearch(): void {
    const q = input.value.trim();
    const roots = getRoots();
    clearHighlights(roots);
    currentIndex = 0;

    if (!q) {
      updateUI();
      return;
    }

    for (const root of roots) {
      highlightInRoot(root, q);
    }

    const marks = allMarks();
    if (marks.length > 0) {
      setActive(0);
    }
    updateUI();
  }

  input.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(runSearch, 200);
  });

  prevBtn.addEventListener('click', () => {
    const marks = allMarks();
    if (marks.length === 0) return;
    setActive(currentIndex - 1);
    updateUI();
  });

  nextBtn.addEventListener('click', () => {
    const marks = allMarks();
    if (marks.length === 0) return;
    setActive(currentIndex + 1);
    updateUI();
  });

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      input.value = '';
      runSearch();
      return;
    }
    if (e.key === 'Enter') {
      e.preventDefault();
      const marks = allMarks();
      if (marks.length === 0) return;
      if (e.shiftKey) {
        setActive(currentIndex - 1);
      } else {
        setActive(currentIndex + 1);
      }
      updateUI();
    }
  });
}
