import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      /**
       * THE APP'S PALETTE IS NOT HERE. It lives in `src/design/tokens.css` as
       * CSS custom properties, and screens reach it with `text-[var(--ink)]`,
       * `bg-[var(--panel)]` and so on.
       *
       * Six flat tokens — `ink`, `paper`, `panel`, `rule`, `verified`,
       * `flagged` — used to sit here and were removed. They were fixed light
       * hexes (`paper` #EDF0F4, `panel` #FBFCFD), so they could not express a
       * theme: `verified` #0E7C55 is 4.8:1 on white and 1.9:1 on the app's
       * `--surface`, which meant the status colour the product cares most
       * about was failing contrast on the theme it actually shipped in. A
       * custom property re-steps per theme under one name; a Tailwind colour
       * cannot.
       *
       * They are deleted rather than aliased to the variables on purpose. An
       * alias would have left two spellings for one colour and no signal about
       * which to use, and the whole reason this migration was needed is that
       * the app had been written against these while the design system it was
       * supposed to be using went unimported.
       */
      colors: {
        /**
         * The landing page's palette, namespaced under `gt-` because it is a
         * different visual world from the authenticated product and the two
         * must not bleed into each other. The app's `--ink` is a custom
         * property in `design/tokens.css` and moves with the theme; `gt-void`
         * is #0A0A0A and belongs to the marketing page, which has no theme.
         *
         * TWO SANCTIONED CROSSINGS, both of them surfaces a visitor meets
         * before they are a user:
         *
         *  1. `gt-electric` on the recruiter flow (`features/recruiter/`),
         *     where it is the primary CTA fill and the match-score band above
         *     70%. That flow's brief named #2563EB as its accent, and #2563EB
         *     is this token — minting a second identical hex under an
         *     app-scoped name would have produced two tokens that must never
         *     disagree. It stays *surfaces and scores* there; status belongs
         *     to `--verified`/`--flagged`.
         *
         *  2. The auth hero (`AuthHero`, `AuthAurora`, and `FIELD_TONE.hero`).
         *     `/login` and `/signup` are the landing page continued through
         *     the door — a dark glass surface in both themes — so the controls
         *     on them are painted in landing tokens rather than app ones. This
         *     crossing was previously undocumented; the code was already doing
         *     it, and the choice is right, so the rule moved rather than the
         *     code.
         *
         * The student flow used to reach for `gt-electric` too, in three
         * files. That one was a genuine leak, not a crossing, and is now
         * `--blue` — which is the same role in the app's palette and, unlike a
         * fixed hex, has a light-theme step.
         *
         * ONE ACCENT, WITH ONE SCOPED EXCEPTION. `gt-electric` is the only
         * accent on the page. `gt-ember` exists solely inside the hero, where
         * it marks verification events on the constellation and ties the
         * overline to them. It must not appear below the fold — outside the
         * hero it has no meaning to carry, and a second accent without a
         * meaning is decoration.
         */
        gt: {
          /* Surfaces. The page alternates void/paper for section rhythm. */
          void: "#0A0A0A",
          /* Footer only — a half-step darker than `void` so the footer reads
             as beneath the page rather than as one more black section. */
          deeper: "#050505",
          paper: "#FFFFFF",

          /* Hero backdrop. A vertical ramp, top to bottom. */
          space: "#050510",
          abyss: "#0A1128",

          /* Accents. */
          electric: "#2563EB",
          ember: "#FF6B35",

          /* The four text tiers, named rather than borrowed from a grey scale
             so no call site has to remember which of neutral/zinc/gray it was
             that happened to match the brief's hex. */
          chalk: "#FAFAFA" /* primary on dark   */,
          ash: "#A1A1AA" /* secondary on dark */,
          slate: "#525252" /* secondary on light */,
          dim: "#71717A" /* tertiary — trust lines, footer legal */,

          /* The one decorative gradient on the page (§09 wash). */
          "wash-from": "#1E40FF",
          "wash-to": "#7C3AED",
        },
      },
      fontFamily: {
        display: ["Archivo", "system-ui", "sans-serif"],
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
        /**
         * The landing page's display face. Deliberately not merged into
         * `display` above: that token is Archivo and is set on every
         * authenticated screen, so redefining it would have restyled the whole
         * product as a side effect of rebuilding one page.
         */
        grotesk: ["Space Grotesk", "Archivo", "system-ui", "sans-serif"],
      },
      /**
       * Fluid type for the landing page. Every size the brief specifies as a
       * desktop/mobile pair is expressed as one clamp instead, so the type
       * scales through the range rather than snapping at a breakpoint — the
       * 88px headline is never rendered at 88px on a 900px-wide laptop, which
       * is the case a fixed pair gets wrong.
       *
       * Each entry carries its own leading and tracking because these sizes are
       * only ever correct together: 96px at default leading would set the
       * stacked wordmark two lines apart.
       */
      fontSize: {
        /* GROUND / TRUTH. 56px → 96px. Leading 0.9 stacks the two lines. */
        "gt-wordmark": [
          "clamp(3.5rem, 8.5vw, 6rem)",
          { lineHeight: "0.9", letterSpacing: "-0.03em" },
        ],
        /* Final CTA. The one headline allowed to match the wordmark's scale. */
        "gt-mega": ["clamp(2.75rem, 7vw, 6rem)", { lineHeight: "0.98", letterSpacing: "-0.03em" }],
        /* Section headlines. 36px mobile → 56px desktop. */
        "gt-h2": [
          "clamp(2.25rem, 4.6vw, 3.5rem)",
          { lineHeight: "1.06", letterSpacing: "-0.02em" },
        ],
        /* Quieter section headlines (§10 trust, §13 FAQ). 48px desktop. */
        "gt-h3": ["clamp(2rem, 3.8vw, 3rem)", { lineHeight: "1.08", letterSpacing: "-0.02em" }],
        /* Stat numerals and pricing figures. 72px desktop. */
        "gt-stat": ["clamp(2.75rem, 5vw, 4.5rem)", { lineHeight: "1", letterSpacing: "-0.03em" }],
        /* Step and card headlines. 24px. */
        "gt-h4": ["1.5rem", { lineHeight: "1.25", letterSpacing: "-0.01em" }],
        /* Hero sub-headline. 22px. */
        "gt-lead": ["1.375rem", { lineHeight: "1.4" }],
        /* Body copy at its two sizes. 1.6 leading per the brief. */
        "gt-body": ["1.125rem", { lineHeight: "1.6" }],
        "gt-body-sm": ["1rem", { lineHeight: "1.6" }],
        /* Overlines. 14px, wide tracking, always uppercase. */
        "gt-over": ["0.875rem", { lineHeight: "1", letterSpacing: "0.12em" }],
        /* The hero's orange overline is smaller and wider than the rest. */
        "gt-over-hero": ["0.75rem", { lineHeight: "1", letterSpacing: "0.15em" }],
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "scale-in": {
          from: { opacity: "0", transform: "scale(0.96) translateY(8px)" },
          to: { opacity: "1", transform: "scale(1) translateY(0)" },
        },
        "slide-up": {
          from: { opacity: "0", transform: "translateY(16px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-8px)" },
        },
        /* The Tier B Smart Apply prompt. `box-shadow` only — no transform and
           no layout property — so the loop stays on the compositor and cannot
           reflow the card it sits in. Call sites drop it entirely under
           `prefers-reduced-motion` rather than shortening it; a looping
           attention animation is the case that setting exists for. */
        "smart-apply-pulse": {
          "0%, 100%": { boxShadow: "0 0 0 0 rgba(37, 99, 235, 0.45)" },
          "50%": { boxShadow: "0 0 0 8px rgba(37, 99, 235, 0)" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.25s ease-out",
        "scale-in": "scale-in 0.25s cubic-bezier(0.16, 1, 0.3, 1)",
        "slide-up": "slide-up 0.4s cubic-bezier(0.16, 1, 0.3, 1)",
        shimmer: "shimmer 2.5s linear infinite",
        float: "float 6s ease-in-out infinite",
        "smart-apply-pulse": "smart-apply-pulse 2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;
