/**
 * The page's animated background.
 *
 * Five fixed layers behind everything: three drifting light fields, a particle
 * constellation dense behind the hero, the blueprint grid that carries the
 * inspection identity, and one slow beam crossing the viewport the way a
 * scanner passes over a document. Together they are what stops a dark page
 * reading as a flat rectangle over a long scroll.
 *
 * Three constraints make it affordable. It is markup and CSS only — no state,
 * no React re-render, no `requestAnimationFrame`, so it costs nothing per
 * frame. Every layer animates `transform` and `opacity` alone, which keeps the
 * whole thing on the compositor. And it is `position: fixed`, so scrolling
 * never repaints it.
 *
 * It carries no information, which is why the page-wide reduced-motion rule is
 * allowed to stop all of it: what remains is the resting composition, and
 * nothing has been said that the reader now misses.
 *
 * Duplicated verbatim in `index.html` so the page's visual world is painted by
 * the stylesheet on first paint rather than arriving with the bundle. Any
 * change here has to be made there too.
 */
export function Backdrop() {
  return (
    <div className="gt-bg" aria-hidden="true">
      <span className="gt-glow gt-glow-a" />
      <span className="gt-glow gt-glow-b" />
      <span className="gt-glow gt-glow-c" />
      <span className="gt-stars" />
      <span className="gt-grid" />
      <span className="gt-beam" />
    </div>
  );
}
