import type { HeroDot, HeroFragment } from "../types";

/** Claim fragments that drift toward the hero's "verified" core. */
export const HERO_FRAGMENTS: HeroFragment[] = [
  { t: '- claims: "5 yrs Python"', cls: "minus", tx: "-190px", ty: "-150px", d: "0s" },
  { t: "- keywords: [react, aws]", cls: "minus", tx: "180px", ty: "-120px", d: "1.1s" },
  { t: '- resume.pdf · "expert"', cls: "minus", tx: "-215px", ty: "60px", d: "2.7s" },
  { t: "+ commit a3f9e21 · retry.py", cls: "plus", tx: "205px", ty: "40px", d: "0.6s" },
  { t: "+ diff --stat  214 ++  38 --", cls: "plus", tx: "-150px", ty: "170px", d: "1.9s" },
  { t: "+ interview: consistent", cls: "plus", tx: "165px", ty: "165px", d: "3.4s" },
];

/** Ambient drifting particles behind the hero fragments. */
export const HERO_DOTS: HeroDot[] = [
  { tx: "-120px", ty: "-190px", d: "0s" },
  { tx: "140px", ty: "-170px", d: "1.4s" },
  { tx: "-230px", ty: "-20px", d: "2.2s" },
  { tx: "235px", ty: "-40px", d: "3s" },
  { tx: "-90px", ty: "200px", d: "3.8s" },
  { tx: "100px", ty: "210px", d: "4.6s" },
];
