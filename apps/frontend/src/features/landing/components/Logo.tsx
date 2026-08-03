/**
 * The wordmark. Type, not an image.
 *
 * There is deliberately no glyph. The page ships with zero image dependencies,
 * which means nothing in the header can fail to load, nothing needs a second
 * asset at 2x, and no placeholder box reserves space for a mark that does not
 * exist yet. A real mark can be dropped in later without touching this layout
 * or the nav's grid.
 *
 * It never animates — not on entry, not on scroll. A wordmark that moves while
 * the reader is trying to identify the product is working against the one job
 * it has.
 */
export function Logo() {
  return (
    <a href="#top" className="logo" aria-label="GroundTruth — home">
      GroundTruth
    </a>
  );
}
