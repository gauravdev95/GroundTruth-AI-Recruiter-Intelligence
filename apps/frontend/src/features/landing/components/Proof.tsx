import { PROOF } from "../content/landing";
import { GroundPlane } from "./GroundPlane";
import { Container } from "./ui/Container";
import { Reveal } from "./ui/Reveal";
import { Section } from "./ui/Section";

/**
 * The strip between the hero and the argument.
 *
 * It carries one sentence and no logos, because there are no customers yet. The
 * brief's alternative line — "join 2,400+ engineers on the early-access
 * waitlist" — is not true, and inventing social proof on the landing page of a
 * product whose entire premise is verified claims would be the single worst
 * available decision.
 *
 * Behind it, the ground plane. The hero hands off a glowing sphere in space and
 * this used to be flat black underneath it, which broke the world in half at
 * the fold. The plane continues it — same blue, same dotted mesh — and it is
 * the literal reading of the product's name, which is worth exactly one section
 * and no more.
 *
 * `bare`, because the canvas has to run full-bleed behind the copy while the
 * copy itself stays on the page's 1280px measure. Taller than a `thin` section
 * would be: a receding plane needs vertical room or it is just a few lines near
 * a horizon.
 */
export function Proof() {
  return (
    <Section
      id="proof"
      label="Early access status"
      tone="void"
      bare
      className="relative isolate overflow-hidden py-28 md:py-36"
    >
      <div aria-hidden="true" className="pointer-events-none absolute inset-0">
        <GroundPlane />
      </div>

      {/*
        A wash from the left, under the copy only. The plane's near rows are its
        brightest and they run straight through where the sentence sits; this
        keeps the text at full contrast without dimming the whole scene.
      */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-y-0 left-0 w-2/3 bg-[linear-gradient(90deg,rgba(10,10,10,0.92)_0%,rgba(10,10,10,0.7)_45%,rgba(10,10,10,0)_100%)]"
      />

      <Container className="relative z-10">
        <Reveal>
          <p className="max-w-[520px] font-sans text-sm text-gt-ash">{PROOF.line}</p>
        </Reveal>
      </Container>
    </Section>
  );
}
