import { MicOff, VideoOff } from "lucide-react";
import { useEffect, type RefObject } from "react";

/**
 * The candidate's own tile — small, corner-pinned, never the focus.
 *
 * Two things it does that a plain `<video>` does not:
 *
 * 1. **Mirrors the preview.** Every video-call product does, because an
 *    unmirrored self-view makes people move the wrong way when they adjust
 *    their framing. It is `scaleX(-1)` on the element only — nothing reads
 *    pixels from here except the obscured-check, which averages luminance and
 *    does not care which way round the frame is.
 * 2. **Shows a real level meter**, driven by an actual analyser on the
 *    microphone stream. Unlike the interviewer's decorative waveform this one
 *    is measuring something, which is what makes it able to answer the question
 *    a candidate actually has: "can it hear me?"
 */

export interface SelfViewProps {
  stream: MediaStream | null;
  videoRef: RefObject<HTMLVideoElement>;
  cameraEnabled: boolean;
  microphoneEnabled: boolean;
  cameraLost: boolean;
  /** 0–1, from `useAudioLevel`. */
  level: number;
  label: string;
}

export function SelfView({
  stream,
  videoRef,
  cameraEnabled,
  microphoneEnabled,
  cameraLost,
  level,
  label,
}: SelfViewProps) {
  useEffect(() => {
    const element = videoRef.current;
    if (!element) return;
    // Assigned imperatively because `srcObject` is not an attribute and cannot
    // be expressed in JSX.
    if (element.srcObject !== stream) element.srcObject = stream;
  }, [stream, videoRef]);

  const showVideo = cameraEnabled && !cameraLost && stream !== null;

  return (
    <div
      className={[
        "relative w-[clamp(160px,18vw,248px)] overflow-hidden rounded-[var(--r-lg)]",
        "border border-[var(--room-rule-strong)] bg-[var(--room-panel)]",
        "shadow-[0_16px_48px_-20px_rgb(0_0_0/0.85)]",
      ].join(" ")}
      style={{ aspectRatio: "4 / 3" }}
    >
      <video
        ref={videoRef}
        autoPlay
        playsInline
        // Muted is mandatory, not a preference: an unmuted self-view plays the
        // candidate's own microphone back through their speakers, which the
        // microphone then picks up.
        muted
        className="h-full w-full object-cover"
        style={{ transform: "scaleX(-1)", opacity: showVideo ? 1 : 0 }}
      />

      {!showVideo ? (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-[var(--room-muted)]">
          <VideoOff size={22} aria-hidden="true" />
          <p className="text-xs">{cameraLost ? "Camera unavailable" : "Camera off"}</p>
        </div>
      ) : null}

      <div className="absolute inset-x-0 bottom-0 flex items-center justify-between gap-2 bg-gradient-to-t from-[rgb(4_6_15/0.85)] to-transparent px-2.5 pb-2 pt-6">
        <span className="truncate text-xs font-medium text-[var(--room-ink)]">{label}</span>

        {microphoneEnabled ? (
          /* Five segments that fill with level. A bar rather than a number:
             nobody reads dB, everybody reads "more green lights when I talk" —
             except this room's rule 1 forbids green, so it is the accent. */
          <span className="flex items-end gap-[3px]" aria-hidden="true">
            {[0.12, 0.28, 0.46, 0.66, 0.85].map((threshold, index) => (
              <span
                key={threshold}
                className="w-[3px] rounded-full transition-colors duration-100"
                style={{
                  height: `${6 + index * 2.5}px`,
                  backgroundColor:
                    level >= threshold ? "var(--room-accent)" : "var(--room-rule-strong)",
                }}
              />
            ))}
          </span>
        ) : (
          <span
            className="flex items-center gap-1 rounded-full bg-[var(--room-danger-dim)] px-1.5 py-0.5 text-[10px] font-medium text-[var(--room-danger)]"
            title="Your microphone is muted"
          >
            <MicOff size={10} aria-hidden="true" /> Muted
          </span>
        )}
      </div>
    </div>
  );
}
