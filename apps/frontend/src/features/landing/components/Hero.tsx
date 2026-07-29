import type { CSSProperties } from "react";
import { ArrowDown, ArrowRight, GitCommitHorizontal, MessageSquare, ShieldCheck } from "lucide-react";

import { HERO_DOTS, HERO_FRAGMENTS } from "../data/heroFragments";

export function Hero() {
  return (
    <header className="hero" id="top">
      <div className="hero-bg" />
      <div className="hero-grid" />
      <div className="wrap hero-in">
        <div>
          <div className="en e1 eyebrow">Engineering talent verification</div>
          <h1 className="h1" style={{ marginTop: 18 }}>
            <span className="line">
              <span className="en e2" style={{ display: "block" }}>
                Resumes claim.
              </span>
            </span>
            <span className="line">
              <span className="en e3" style={{ display: "block" }}>
                Code <span className="serif">proves.</span>
              </span>
            </span>
          </h1>
          <p className="hero-sub en e4">
            GroundTruth AI reads a candidate's real GitHub work — commit by commit — interviews
            them on their own code, and compiles an explainable Engineering Evidence Profile your
            team can actually trust.
          </p>
          <div className="hero-ctas en e5">
            <a className="btn" href="#profile">
              See a Sample Evidence Profile <ArrowRight size={17} />
            </a>
            <a className="ghost" href="#how">
              How it works <ArrowDown size={16} />
            </a>
          </div>
          <div className="hero-note en e5">
            <span className="pill">
              <GitCommitHorizontal size={13} /> Commit-level analysis
            </span>
            <span className="pill">
              <MessageSquare size={13} /> Adaptive AI interview
            </span>
            <span className="pill">
              <ShieldCheck size={13} /> Evidence-backed profiles
            </span>
          </div>
        </div>

        {/* Signature object — unverified claims resolving into proven evidence */}
        <div className="stage stage-en" aria-hidden="true">
          <div className="stage-light" />
          <div className="stage-floor" />
          <div
            className="float"
            style={{
              position: "relative",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <div className="stack-card sc1" />
            <div className="stack-card sc2" />
            {HERO_DOTS.map((p, i) => (
              <span
                key={i}
                className="dot"
                style={{ "--tx": p.tx, "--ty": p.ty, animationDelay: p.d } as CSSProperties}
              />
            ))}
            {HERO_FRAGMENTS.map((f, i) => (
              <span
                key={i}
                className={`frag ${f.cls}`}
                style={{ "--tx": f.tx, "--ty": f.ty, animationDelay: f.d } as CSSProperties}
              >
                {f.t}
              </span>
            ))}
            <div className="core">
              <svg width="72" height="72" viewBox="0 0 72 72" fill="none">
                <path
                  d="M14 38 L29 53 L58 20"
                  stroke="url(#coreg)"
                  strokeWidth="7"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <defs>
                  <linearGradient id="coreg" x1="14" y1="50" x2="58" y2="20" gradientUnits="userSpaceOnUse">
                    <stop stopColor="#4F46E5" />
                    <stop offset="1" stopColor="#7C3AED" />
                  </linearGradient>
                </defs>
              </svg>
              <span className="core-label">VERIFIED</span>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
