import { useState } from "react";

/**
 * The interviewer's face.
 *
 * ## Flagged: this ships as a rendered portrait, not a photograph
 *
 * The brief asks for a professional, human-looking, photo-realistic interviewer
 * on a neutral office background. A photograph cannot be authored here — there
 * is no licensed asset in the repository, and inventing a face for a product
 * that assesses real people is a decision about the product's voice, not a
 * frontend detail. So this ships a composed portrait: a softly lit figure at a
 * desk, in the room's own palette, at the scale and framing a webcam tile would
 * have. It reads as a considered visual, not as a cartoon and not as a robot.
 *
 * **To use a real portrait, drop one in and nothing else changes.** Put a file
 * at `public/interviewer-portrait.jpg`, or point `VITE_INTERVIEWER_PORTRAIT` at
 * any same-origin path. It is used if it loads and this is the fallback if it
 * does not — `onError` is the whole switch, so a missing asset degrades to a
 * drawn portrait rather than to a broken image icon in the middle of an
 * interview.
 *
 * Whatever is used, the framing is the same: head and shoulders, slightly off
 * centre, eyes on the upper third. That is where a person sits in a video tile,
 * and getting it wrong is most of what makes an avatar feel wrong.
 */

const PORTRAIT_SRC =
  (import.meta.env.VITE_INTERVIEWER_PORTRAIT as string | undefined) ??
  "/interviewer-portrait.jpg";

export interface InterviewerPortraitProps {
  /** Drives the subtle warmth of the key light — the interviewer looks a
   * fraction more "present" while speaking. Never more than that: an avatar
   * that emotes is an avatar that distracts. */
  speaking: boolean;
  className?: string;
}

export function InterviewerPortrait({ speaking, className }: InterviewerPortraitProps) {
  const [photoFailed, setPhotoFailed] = useState(false);

  if (!photoFailed) {
    return (
      <img
        src={PORTRAIT_SRC}
        alt=""
        aria-hidden="true"
        onError={() => setPhotoFailed(true)}
        className={["h-full w-full object-cover", className ?? ""].join(" ")}
        draggable={false}
      />
    );
  }

  return (
    <svg
      viewBox="0 0 400 400"
      className={["h-full w-full", className ?? ""].join(" ")}
      aria-hidden="true"
      preserveAspectRatio="xMidYMid slice"
    >
      <defs>
        {/* The office behind them. A vertical ramp plus one off-centre window
            light — the two things that stop a flat fill reading as a backdrop
            rather than a room. */}
        <linearGradient id="room-wall" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#16203a" />
          <stop offset="100%" stopColor="#0a0f1d" />
        </linearGradient>
        <radialGradient id="room-window" cx="0.76" cy="0.24" r="0.6">
          <stop offset="0%" stopColor="#31456e" stopOpacity="0.85" />
          <stop offset="100%" stopColor="#31456e" stopOpacity="0" />
        </radialGradient>
        {/* Key light on the subject, from the same side as the window. */}
        <linearGradient id="room-skin" x1="0.25" y1="0" x2="0.85" y2="1">
          <stop offset="0%" stopColor="#d9b49a" />
          <stop offset="55%" stopColor="#bd9179" />
          <stop offset="100%" stopColor="#8e6a58" />
        </linearGradient>
        <linearGradient id="room-hair" x1="0.3" y1="0" x2="0.8" y2="1">
          <stop offset="0%" stopColor="#3a3040" />
          <stop offset="100%" stopColor="#1c1722" />
        </linearGradient>
        <linearGradient id="room-jacket" x1="0.2" y1="0" x2="0.9" y2="1">
          <stop offset="0%" stopColor="#2c3854" />
          <stop offset="100%" stopColor="#161d2e" />
        </linearGradient>
        <linearGradient id="room-shirt" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#e6ecf7" />
          <stop offset="100%" stopColor="#b9c4d8" />
        </linearGradient>
      </defs>

      {/* -- the room ------------------------------------------------------ */}
      <rect width="400" height="400" fill="url(#room-wall)" />
      <rect width="400" height="400" fill="url(#room-window)" />
      {/* A single out-of-focus shelf line. One piece of set dressing reads as
          an office; three read as a stock illustration. */}
      <rect x="248" y="150" width="152" height="3" fill="#3d4c72" opacity="0.28" rx="1.5" />
      <rect x="266" y="122" width="26" height="28" fill="#3d4c72" opacity="0.2" rx="2" />
      <rect x="298" y="128" width="18" height="22" fill="#3d4c72" opacity="0.16" rx="2" />

      {/* -- the figure ---------------------------------------------------- */}
      {/* Shoulders first, so the head overlaps them the way a head does. */}
      <path
        d="M 78 400 C 82 322 128 288 200 288 C 272 288 318 322 322 400 Z"
        fill="url(#room-jacket)"
      />
      {/* Collar and shirt. */}
      <path d="M 168 292 L 200 348 L 232 292 L 214 284 L 200 320 L 186 284 Z" fill="url(#room-shirt)" />
      <path d="M 166 290 L 200 350 L 178 300 Z" fill="#1b2338" opacity="0.5" />
      <path d="M 234 290 L 200 350 L 222 300 Z" fill="#1b2338" opacity="0.5" />

      {/* Neck. */}
      <path d="M 178 250 L 178 296 Q 200 312 222 296 L 222 250 Z" fill="#a97e69" />
      <path d="M 178 250 L 178 272 Q 200 286 222 272 L 222 250 Z" fill="#8e6a58" opacity="0.55" />

      {/* Head. */}
      <ellipse cx="200" cy="196" rx="62" ry="74" fill="url(#room-skin)" />
      {/* Hair: a short professional cut, sitting on the skull rather than
          drawn as a shape beside it. */}
      <path
        d="M 138 190 C 136 138 162 112 200 112 C 238 112 264 138 262 190 C 258 168 248 150 234 146 C 216 158 184 158 166 146 C 152 150 142 168 138 190 Z"
        fill="url(#room-hair)"
      />
      {/* Brows, eyes, nose, mouth. Minimal and symmetrical — every extra line
          here moves the drawing toward caricature. */}
      <rect x="166" y="182" width="26" height="4" rx="2" fill="#4a3a35" opacity="0.75" />
      <rect x="208" y="182" width="26" height="4" rx="2" fill="#4a3a35" opacity="0.75" />
      <ellipse cx="179" cy="198" rx="7" ry="5.5" fill="#f2f4f8" />
      <ellipse cx="221" cy="198" rx="7" ry="5.5" fill="#f2f4f8" />
      <circle cx="179.5" cy="198.5" r="3.4" fill="#3c2f2a" />
      <circle cx="221.5" cy="198.5" r="3.4" fill="#3c2f2a" />
      <circle cx="181" cy="197" r="1.1" fill="#ffffff" opacity="0.9" />
      <circle cx="223" cy="197" r="1.1" fill="#ffffff" opacity="0.9" />
      <path
        d="M 198 206 L 196 224 Q 200 227 204 224 L 202 206"
        fill="none"
        stroke="#8e6a58"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      {/* The mouth opens a little while speaking. One property, two states —
          the whole of the "subtle avatar movement" the brief asks for, and
          none of the lip-sync theatre it explicitly rules out. */}
      <path
        d={speaking ? "M 184 242 Q 200 256 216 242 Q 200 250 184 242 Z" : "M 184 243 Q 200 251 216 243"}
        fill={speaking ? "#6d4a44" : "none"}
        stroke="#7a5347"
        strokeWidth="2.5"
        strokeLinecap="round"
        style={{ transition: "d 160ms ease-out" }}
      />
      {/* Ambient occlusion under the jaw, which is most of what stops a flat
          vector head reading as a sticker. */}
      <ellipse cx="200" cy="268" rx="40" ry="12" fill="#5d4038" opacity="0.35" />

      {/* A warm rim on the lit side, brought up a touch while speaking. */}
      <path
        d="M 246 156 C 262 176 262 216 246 240"
        fill="none"
        stroke="#ffd9b0"
        strokeWidth="4"
        strokeLinecap="round"
        opacity={speaking ? 0.34 : 0.2}
        style={{ transition: "opacity 400ms ease-out" }}
      />
    </svg>
  );
}
