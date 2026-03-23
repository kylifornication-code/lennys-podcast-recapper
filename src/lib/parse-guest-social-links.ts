/**
 * Extract guest social / web links from the YouTube description block
 * between "Where to find {guest}:" and "Where to find Lenny:".
 */

export type SocialPlatform =
  | 'x'
  | 'linkedin'
  | 'website'
  | 'newsletter'
  | 'books'
  | 'instagram'
  | 'github'
  | 'youtube'
  | 'threads'
  | 'other';

export interface GuestSocialLink {
  platform: SocialPlatform;
  label: string;
  href: string;
}

function normalizeHeading(s: string): string {
  return s
    .replace(/\*/g, '')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, ' ');
}

function isLennyHeading(heading: string): boolean {
  const n = normalizeHeading(heading);
  return n === 'lenny' || n.startsWith('lenny ') || n.includes('lenny rachitsky');
}

function trimUrl(url: string): string {
  return url.replace(/[.,;:!?)]+$/, '').replace(/&quot;$/i, '');
}

function classifyPlatform(labelRaw: string, href: string): SocialPlatform {
  const label = labelRaw.trim().toLowerCase();
  const u = href.toLowerCase();

  if (label === 'x' || label.includes('twitter')) return 'x';
  if (label.includes('linkedin') || u.includes('linkedin.com')) return 'linkedin';
  if (label.includes('newsletter') || u.includes('substack.com') || /substack/i.test(label)) return 'newsletter';
  if (label.includes('reading') || label.includes('book')) return 'books';
  if (label.includes('instagram') || u.includes('instagram.com')) return 'instagram';
  if (label.includes('github') || u.includes('github.com')) return 'github';
  if (label.includes('youtube') || u.includes('youtube.com') || u.includes('youtu.be')) return 'youtube';
  if (label.includes('threads') || u.includes('threads.net')) return 'threads';
  if (label.includes('website') || label.includes('web site') || label === 'site' || label.includes('homepage'))
    return 'website';
  if (u.includes('lennysnewsletter.com')) return 'newsletter';

  if (u.includes('twitter.com') || u.includes('x.com')) return 'x';

  return 'website';
}

const WHERE_HEADING =
  /(?:^|\r?\n)\s*\*?\s*Where to find\s+([^:*\r\n]+?)\s*:\s*\*?\s*/gi;

/**
 * Text before the Lenny "Where to find" section.
 */
function sliceBeforeLenny(description: string): string {
  const m = description.match(/\r?\n\s*\*?\s*Where to find\s+lenny\s*:\s*\*?\s*/i);
  if (!m || m.index === undefined) return description;
  return description.slice(0, m.index);
}

/**
 * All guest "Where to find" sections before Lenny (excluding Lenny); bullets merged, URLs deduped.
 */
export function parseGuestSocialLinks(description: string): GuestSocialLink[] {
  const raw = description.trim();
  if (!raw) return [];

  const region = sliceBeforeLenny(raw);
  const matches = [...region.matchAll(WHERE_HEADING)];

  const seen = new Set<string>();
  const out: GuestSocialLink[] = [];

  for (let i = 0; i < matches.length; i++) {
    const m = matches[i];
    const heading = m[1].replace(/\*/g, '').trim();
    if (!heading || isLennyHeading(heading)) continue;

    const start = m.index! + m[0].length;
    const end = i + 1 < matches.length ? matches[i + 1].index! : region.length;
    const body = region.slice(start, end);

    for (const line of body.split(/\r?\n/)) {
      const bullet = line.match(/^\s*[•\u2022\-*]\s*(.+?):\s*(https?:\/\/\S+)/i);
      if (!bullet) continue;

      const label = bullet[1].replace(/\*/g, '').trim();
      const href = trimUrl(bullet[2]);
      if (!href) continue;

      const key = href.toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);

      out.push({
        platform: classifyPlatform(label, href),
        label,
        href,
      });
    }
  }

  return out;
}
