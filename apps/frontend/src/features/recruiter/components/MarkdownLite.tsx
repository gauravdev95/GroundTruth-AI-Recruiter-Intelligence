import { Fragment } from "react";

/**
 * The two pieces of markdown the job-description field advertises: `**bold**`
 * and `-` bullets. Nothing else.
 *
 * **Deliberately not a markdown library, and deliberately not
 * `dangerouslySetInnerHTML`.** This renders text a recruiter typed into a
 * field on a screen another recruiter reads, which is not a trust boundary
 * worth testing — every fragment below is a React child, so the escaping is
 * structural rather than something a sanitiser has to get right. The cost is
 * that headings and links do not render; the description field never offered
 * them.
 */

const BOLD = /\*\*(.+?)\*\*/g;

function inline(text: string, keyPrefix: string) {
  const parts: React.ReactNode[] = [];
  let cursor = 0;
  let match: RegExpExecArray | null;

  BOLD.lastIndex = 0;
  while ((match = BOLD.exec(text)) !== null) {
    if (match.index > cursor) parts.push(text.slice(cursor, match.index));
    parts.push(
      <strong key={`${keyPrefix}-b${match.index}`} className="font-semibold text-[var(--ink)]">
        {match[1]}
      </strong>,
    );
    cursor = match.index + match[0].length;
  }
  if (cursor < text.length) parts.push(text.slice(cursor));
  return parts;
}

export function MarkdownLite({ text }: { text: string }) {
  const lines = text.split(/\r?\n/);
  const blocks: React.ReactNode[] = [];
  let bullets: string[] = [];

  const flushBullets = (key: string) => {
    if (bullets.length === 0) return;
    blocks.push(
      <ul key={`ul-${key}`} className="my-2 list-disc space-y-1 pl-5">
        {bullets.map((item, index) => (
          <li key={index}>{inline(item, `${key}-${index}`)}</li>
        ))}
      </ul>,
    );
    bullets = [];
  };

  lines.forEach((line, index) => {
    const trimmed = line.trim();
    const bullet = /^[-*]\s+(.*)$/.exec(trimmed);
    if (bullet) {
      bullets.push(bullet[1]);
      return;
    }
    flushBullets(String(index));
    if (trimmed === "") return;
    blocks.push(
      <p key={`p-${index}`} className="my-2">
        {inline(trimmed, String(index))}
      </p>,
    );
  });
  flushBullets("end");

  return <Fragment>{blocks}</Fragment>;
}
