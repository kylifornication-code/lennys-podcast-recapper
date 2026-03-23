/**
 * Turn YouTube-style description markup (*sections*, _italics_, **bold**) into safe HTML.
 * URLs become clickable links.
 */

const EM_BLOCK = '\uE000';
const EM_END = '\uE001';

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function linkifyUrl(raw: string): string {
  const href = raw.replace(/[.,;:!?)\]]+$/, '');
  const e = escapeHtml(href);
  return `<a href="${e}" target="_blank" rel="noopener noreferrer">${e}</a>`;
}

/** Linkify https URLs in already-escaped text (no HTML tags yet). */
function linkifyEscapedPlain(escaped: string): string {
  return escaped.replace(/(https?:\/\/[^\s<]+)/g, (url) => {
    const trimmed = url.replace(/[.,;:!?)\]]+$/, '');
    const e = escapeHtml(trimmed);
    return `<a href="${e}" target="_blank" rel="noopener noreferrer">${e}</a>`;
  });
}

function splitUrls(text: string): { type: 'text' | 'url'; v: string }[] {
  const parts = text.split(/(https?:\/\/[^\s<]+)/g);
  const out: { type: 'text' | 'url'; v: string }[] = [];
  for (let i = 0; i < parts.length; i++) {
    const p = parts[i];
    if (p === '') continue;
    if (i % 2 === 1) out.push({ type: 'url', v: p });
    else out.push({ type: 'text', v: p });
  }
  return out;
}

/**
 * Bold (** / *) on plain text; preserves existing <em>…</em> blocks unescaped.
 */
function formatTextSegmentBoldOnly(text: string): string {
  const parts = text.split(/(<em>[\s\S]*?<\/em>)/g);
  return parts
    .map((part) => {
      if (part.startsWith('<em>')) return part;
      let s = escapeHtml(part);
      s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
      s = s.replace(/\*([^*]+)\*/g, '<strong>$1</strong>');
      return s;
    })
    .join('');
}

/**
 * 1) _italic_ pairs (may contain URLs) → <em>…</em> via placeholders so later URL split
 *    never sees raw https inside <a>.
 * 2) splitUrls on the mixed string.
 * 3) Bold on remaining text segments.
 */
function formatTextSegmentWithInlineMarkup(text: string): string {
  const placeholders: string[] = [];

  let s = text.replace(/_([^_\n]+)_/g, (_, inner) => {
    const e = escapeHtml(inner);
    const linked = linkifyEscapedPlain(e);
    const html = `<em>${linked}</em>`;
    placeholders.push(html);
    return `${EM_BLOCK}${placeholders.length - 1}${EM_END}`;
  });

  const pieces = splitUrls(s);
  return pieces
    .map((p) => {
      if (p.type === 'url') return linkifyUrl(p.v);
      let t = p.v;
      t = t.replace(new RegExp(`${EM_BLOCK}(\\d+)${EM_END}`, 'g'), (_, i) => placeholders[Number(i)] ?? '');
      return formatTextSegmentBoldOnly(t);
    })
    .join('');
}

function formatLine(line: string): string {
  const t = line.trim();
  if (!t) return '';

  if (/^\*[^*]+\*$/.test(t)) {
    const label = t.slice(1, -1);
    return `<p class="episode-description-section">${formatTextSegmentWithInlineMarkup(label)}</p>`;
  }

  return `<p class="episode-description-line">${formatTextSegmentWithInlineMarkup(t)}</p>`;
}

export function formatYoutubeDescriptionHtml(raw: string): string {
  const text = raw.trim();
  if (!text) return '';

  const lines = text.split('\n');
  const blocks: string[] = [];

  for (const line of lines) {
    const formatted = formatLine(line);
    if (formatted) blocks.push(formatted);
    else blocks.push('<br />');
  }

  return blocks.join('');
}
