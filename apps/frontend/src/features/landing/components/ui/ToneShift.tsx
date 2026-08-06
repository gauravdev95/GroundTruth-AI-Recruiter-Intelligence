/**
 * The band that carries the page across a black/white section boundary.
 *
 * Most tone changes on this page are a hard edge, and that is deliberate — the
 * abrupt black/white boundary is the rhythm the whole layout is built on. Two
 * crossings get this treatment instead, and both for the same reason: they are
 * the ones where a reader is moving between two *large* blocks of opposite tone
 * mid-argument, where a hard cut reads as two pages stapled together rather
 * than as one page changing register.
 *
 * Three stops, not two, in both directions. Black straight to white greys out
 * through the middle and looks like a rendering artefact; routing the ramp
 * through the page's own electric blue gives it a hue to travel along and ties
 * the transition to the accent instead of introducing a new colour to do the
 * job. The `toDark` ramp is the same path walked backwards, so the two
 * crossings are visibly the same device.
 *
 * `aria-hidden` and 80px tall: it carries no content, and no reader should ever
 * land on it from an anchor jump.
 */
export function ToneShift({ direction }: { direction: "toLight" | "toDark" }) {
  return (
    <div
      aria-hidden="true"
      className={
        direction === "toLight"
          ? "h-20 w-full bg-[linear-gradient(180deg,#0A0A0A_0%,#101A3D_38%,#2E49B8_62%,#FFFFFF_100%)]"
          : "h-20 w-full bg-[linear-gradient(180deg,#FFFFFF_0%,#2E49B8_38%,#101A3D_62%,#0A0A0A_100%)]"
      }
    />
  );
}
