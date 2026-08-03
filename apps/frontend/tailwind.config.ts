import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      /**
       * The same six tokens the landing page's stylesheet defines, exposed to
       * Tailwind so auth and dashboard screens share one identity with it.
       *
       * `verified` and `flagged` keep their landing meaning everywhere: green
       * is proven by an artefact, amber is claimed but unchecked. Outside that
       * meaning they are only ever used for focus rings, never for decoration.
       */
      colors: {
        ink: { DEFAULT: "#0A1628", hover: "#12233C" },
        paper: "#EDF0F4",
        panel: "#FBFCFD",
        rule: "#D3DAE3",
        verified: "#0E7C55",
        flagged: "#9A5B08",
      },
      fontFamily: {
        display: ["Archivo", "system-ui", "sans-serif"],
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
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
      },
      animation: {
        "fade-in": "fade-in 0.25s ease-out",
        "scale-in": "scale-in 0.25s cubic-bezier(0.16, 1, 0.3, 1)",
        "slide-up": "slide-up 0.4s cubic-bezier(0.16, 1, 0.3, 1)",
        shimmer: "shimmer 2.5s linear infinite",
        float: "float 6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;
