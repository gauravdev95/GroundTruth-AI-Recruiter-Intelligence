import { AnimatePresence, motion } from "framer-motion";
import { Menu, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { DURATION, EASE, useReducedMotionSafe } from "@/design/motion";
import { cn } from "@/lib/utils";

import { NAV, NAV_LINKS } from "../content/landing";
import { Button } from "./ui/Button";
import { Container } from "./ui/Container";

/**
 * Scroll distance after which the nav stops being transparent.
 *
 * Deliberately short. The switch should happen as the hero's top edge leaves,
 * not when the hero does — a bar that is still transparent halfway down a white
 * section has invisible links in it.
 */
const SOLID_AFTER = 80;

/**
 * The wordmark. A filled dot, then the name.
 *
 * The dot is electric blue, not the hero's orange. Orange on this page means
 * "a verification event on the constellation" and it lives inside the hero for
 * that reason; the nav outlives the hero by twelve sections, so a permanent
 * orange mark would carry the meaning somewhere it cannot be true.
 */
function Wordmark({ solid }: { solid: boolean }) {
  return (
    <a
      href="#top"
      aria-label={NAV.homeLabel}
      className={cn(
        "group inline-flex items-center gap-2.5 rounded-sm font-grotesk text-xl font-bold tracking-tight",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gt-electric focus-visible:ring-offset-4",
        solid
          ? "text-gt-void focus-visible:ring-offset-gt-paper"
          : "text-white focus-visible:ring-offset-transparent",
      )}
    >
      <span aria-hidden="true" className="h-2 w-2 rounded-full bg-gt-electric" />
      GroundTruth
    </a>
  );
}

export function Nav() {
  const [solid, setSolid] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const reduced = useReducedMotionSafe();
  const burgerRef = useRef<HTMLButtonElement>(null);

  /*
   * A passive scroll listener rather than the shared rAF loop. The loop only
   * runs while something is subscribed to it, and subscribing a boolean check
   * for the lifetime of the page would keep it running forever — including
   * while the reader sits still, which is most of the time. This costs nothing
   * when nobody is scrolling, and `setSolid` only re-renders on the crossing.
   */
  useEffect(() => {
    const onScroll = () => setSolid(window.scrollY > SOLID_AFTER);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  /* Escape closes the sheet and returns focus to the control that opened it. */
  useEffect(() => {
    if (!menuOpen) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setMenuOpen(false);
      burgerRef.current?.focus();
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [menuOpen]);

  /* An open sheet must not scroll the page behind it. */
  useEffect(() => {
    if (!menuOpen) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [menuOpen]);

  const linkClass = cn(
    "rounded-sm font-sans text-sm transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gt-electric focus-visible:ring-offset-4",
    solid
      ? "text-gt-slate hover:text-gt-void focus-visible:ring-offset-gt-paper"
      : "text-white/70 hover:text-white focus-visible:ring-offset-transparent",
  );

  return (
    <nav
      aria-label="Primary"
      className={cn(
        "fixed inset-x-0 top-0 z-50 h-[72px] transition-colors duration-300 ease-out",
        solid || menuOpen
          ? "border-b border-black/10 bg-gt-paper"
          : "border-b border-transparent bg-transparent",
      )}
    >
      <Container className="flex h-full items-center justify-between gap-8">
        <Wordmark solid={solid || menuOpen} />

        <div className="hidden items-center gap-8 lg:flex">
          {NAV_LINKS.map((link) => (
            <a key={link.href} href={link.href} className={linkClass}>
              {link.label}
            </a>
          ))}
        </div>

        <div className="hidden items-center gap-6 lg:flex">
          <a href={NAV.logIn.href} className={linkClass}>
            {NAV.logIn.label}
          </a>
          <Button href={NAV.cta.href} size="sm" tone={solid ? "light" : "dark"}>
            {NAV.cta.label}
          </Button>
        </div>

        <button
          ref={burgerRef}
          type="button"
          onClick={() => setMenuOpen((open) => !open)}
          aria-expanded={menuOpen}
          aria-controls="gt-nav-sheet"
          aria-label={menuOpen ? NAV.closeMenu : NAV.openMenu}
          className={cn(
            "rounded-md p-2 transition-colors duration-200 lg:hidden",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gt-electric focus-visible:ring-offset-2",
            solid || menuOpen ? "text-gt-void focus-visible:ring-offset-gt-paper" : "text-white",
          )}
        >
          {menuOpen ? <X size={20} aria-hidden="true" /> : <Menu size={20} aria-hidden="true" />}
        </button>
      </Container>

      <AnimatePresence>
        {menuOpen && (
          <motion.div
            id="gt-nav-sheet"
            initial={reduced ? false : { opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={reduced ? { opacity: 1 } : { opacity: 0, y: -8 }}
            transition={{ duration: DURATION.fast, ease: EASE.standard }}
            className="absolute inset-x-0 top-[72px] border-b border-black/10 bg-gt-paper lg:hidden"
          >
            <Container className="flex flex-col gap-1 py-6">
              {NAV_LINKS.map((link) => (
                <a
                  key={link.href}
                  href={link.href}
                  onClick={() => setMenuOpen(false)}
                  className="rounded-md px-2 py-3 font-sans text-gt-body-sm text-gt-void focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gt-electric"
                >
                  {link.label}
                </a>
              ))}

              <div className="mt-4 flex flex-col gap-3 border-t border-black/10 pt-6">
                <a
                  href={NAV.logIn.href}
                  className="rounded-md px-2 py-2 font-sans text-gt-body-sm text-gt-slate focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gt-electric"
                >
                  {NAV.logIn.label}
                </a>
                <Button href={NAV.cta.href} block>
                  {NAV.cta.label}
                </Button>
              </div>
            </Container>
          </motion.div>
        )}
      </AnimatePresence>
    </nav>
  );
}
