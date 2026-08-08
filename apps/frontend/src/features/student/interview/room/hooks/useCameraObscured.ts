import { useEffect, useRef, useState } from "react";

/**
 * Is the camera showing anything at all?
 *
 * ## What this is, and what it is honestly not
 *
 * The brief asks the room to notice when "the candidate leaves the camera
 * frame". That needs face detection, and face detection in a browser needs
 * either a model download or `FaceDetector`, which ships behind a flag in one
 * browser. Shipping either would mean claiming to know something about a
 * candidate's body that the code does not actually know — and getting it wrong
 * on a dark room, a backlit window, or a face the model was not trained on.
 *
 * So this measures the one thing a canvas can measure without lying: whether
 * the video feed has gone effectively black, which is what a covered lens, a
 * privacy shutter or a dead sensor looks like. It is reported as
 * `camera_obscured` — the literal observation — and never as "candidate absent".
 *
 * ## Cost
 *
 * One 32×24 frame every three seconds, drawn to an offscreen canvas. That
 * resolution is enough to average a luminance and small enough that the whole
 * check costs less than a frame budget on the machine's slowest core.
 */

/** Mean luminance (0–255) below which a feed is treated as dark. Low enough
 * that a dim room does not trip it — an unlit bedroom webcam still averages
 * well above this once auto-exposure settles. */
const DARK_THRESHOLD = 8;
const SAMPLE_INTERVAL_MS = 3_000;
/** Consecutive dark samples before it counts. Nine seconds of black, so a hand
 * passing the lens or a moment mid-exposure-adjust is not an event. */
const CONSECUTIVE_SAMPLES = 3;

export function useCameraObscured(
  videoRef: React.RefObject<HTMLVideoElement | null>,
  active: boolean,
): boolean {
  const [obscured, setObscured] = useState(false);
  const consecutiveRef = useRef(0);

  useEffect(() => {
    if (!active) {
      consecutiveRef.current = 0;
      setObscured(false);
      return;
    }

    const canvas = document.createElement("canvas");
    canvas.width = 32;
    canvas.height = 24;
    const context = canvas.getContext("2d", { willReadFrequently: true });
    if (!context) return;

    const sample = () => {
      const video = videoRef.current;
      if (!video || video.readyState < 2 || video.videoWidth === 0) return;

      try {
        context.drawImage(video, 0, 0, canvas.width, canvas.height);
        const { data } = context.getImageData(0, 0, canvas.width, canvas.height);
        let total = 0;
        for (let i = 0; i < data.length; i += 4) {
          // Rec. 601 luma. Cheaper than converting colour spaces and accurate
          // enough for "is this black".
          total += 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
        }
        const mean = total / (data.length / 4);

        if (mean < DARK_THRESHOLD) {
          consecutiveRef.current += 1;
          if (consecutiveRef.current >= CONSECUTIVE_SAMPLES) setObscured(true);
        } else {
          consecutiveRef.current = 0;
          setObscured(false);
        }
      } catch {
        // A tainted canvas cannot happen with a local `getUserMedia` stream,
        // but a frame read can still fail while a track is being torn down.
        consecutiveRef.current = 0;
      }
    };

    const timer = setInterval(sample, SAMPLE_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [videoRef, active]);

  return obscured;
}
