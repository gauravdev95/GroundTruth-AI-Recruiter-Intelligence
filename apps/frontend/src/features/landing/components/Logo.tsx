interface GlyphProps {
  size?: number;
}

/** GroundTruth AI mark — code brackets fused with a verification check. */
function Glyph({ size = 26 }: GlyphProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <path
        d="M10 9 L4 16 L10 23"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M22 9 L28 16 L22 23"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M11.5 16.2 L15 19.6 L20.5 12"
        stroke="url(#gtg)"
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="11.5" cy="16.2" r="1.5" fill="url(#gtg)" />
      <defs>
        <linearGradient id="gtg" x1="11" y1="20" x2="21" y2="12" gradientUnits="userSpaceOnUse">
          <stop stopColor="#4F46E5" />
          <stop offset="1" stopColor="#7C3AED" />
        </linearGradient>
      </defs>
    </svg>
  );
}

export function Logo() {
  return (
    <a href="#top" className="logo" aria-label="GroundTruth AI — home">
      <Glyph />
      <span>
        GroundTruth&nbsp;<span className="ai">AI</span>
      </span>
    </a>
  );
}
