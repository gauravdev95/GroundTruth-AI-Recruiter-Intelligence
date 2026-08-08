import { useEffect, useRef, useState } from "react";

/**
 * How loud the microphone is, 0–1, sampled on animation frames.
 *
 * Two jobs, and it is worth being clear that it does only these two:
 *
 * 1. **The level meter on the control bar and the self-view.** A candidate
 *    needs to be able to see that their microphone is working without saying
 *    "can you hear me?" to a machine that will treat it as an answer.
 * 2. **Detecting a stretch with no audio at all**, which the room reports as an
 *    integrity signal — a microphone that has been muted at the OS level looks
 *    exactly like a candidate who has stopped talking, and both are worth a
 *    gentle nudge before ten minutes go by.
 *
 * It does **not** decide when a turn is over. That is the recogniser's job
 * (`useSpeechRecognition`), because volume cannot tell speech from a passing
 * lorry and an interview that replied to road noise would be worse than one
 * that waited.
 *
 * RMS rather than peak: peak jumps on every consonant, which produces a meter
 * that flickers rather than one that reads as a voice.
 */

const SILENCE_THRESHOLD = 0.015;

export interface AudioLevelState {
  /** Smoothed RMS, 0–1. */
  level: number;
  /** True while the level has been under the noise floor continuously. Reset
   * the moment anything is heard. */
  silent: boolean;
  /** How long it has been silent, in seconds. */
  silentForSeconds: number;
  /** Loudest level seen since this stream was attached. The meter shows the
   * instant; this answers "has this microphone *ever* produced audio", which is
   * the question worth asking when nothing seems to be happening. */
  peak: number;
  /** Why nothing is being heard, when nothing is being heard — or null when
   * audio is arriving normally.
   *
   * This exists because every failure in this layer is silent by nature. A
   * suspended context, an OS-muted device and a candidate who simply has not
   * spoken yet all produce the same thing: zeros. Naming which one it is turns
   * an unexplainable dead meter into an instruction. */
  diagnosis: AudioDiagnosis | null;
}

export interface AudioDiagnosis {
  code: "context_suspended" | "track_muted" | "track_ended" | "track_disabled" | "no_signal";
  message: string;
  detail: string;
}

/** How long a granted-but-silent microphone waits before the hook stops
 * assuming the candidate is just thinking and starts reporting a fault. */
const DIAGNOSE_AFTER_SECONDS = 4;

/**
 * Why is this microphone producing nothing?
 *
 * Checked in the order a person would fix them. `track.muted` is the one worth
 * knowing about: it is **not** the same as `track.enabled`, which is the
 * in-page mute button. `muted` is set by the *source* — the operating system's
 * own mute, a hardware switch on a headset, or another application taking
 * exclusive control — and it is the single most common cause of a browser
 * microphone that has permission, reports `live`, and delivers pure silence.
 */
function diagnose(context: AudioContext, stream: MediaStream): AudioDiagnosis {
  if (context.state !== "running") {
    return {
      code: "context_suspended",
      message: "Your browser paused audio processing for this page.",
      detail: `AudioContext is "${context.state}". Click anywhere on the page, then try again.`,
    };
  }

  const track = stream.getAudioTracks()[0];
  if (!track) {
    return {
      code: "track_ended",
      message: "No microphone track is attached.",
      detail: "The stream has no audio track. Reconnect your microphone and check again.",
    };
  }
  if (track.readyState === "ended") {
    return {
      code: "track_ended",
      message: "Your microphone stopped.",
      detail: `Track "${track.label || "unknown device"}" has ended. Reconnect it and check again.`,
    };
  }
  if (track.muted) {
    return {
      code: "track_muted",
      message: "Your microphone is muted outside the browser.",
      detail:
        `Windows or your headset is muting "${track.label || "your microphone"}". ` +
        "Check the mute key on your keyboard or headset, and Windows Sound settings › Input.",
    };
  }
  if (!track.enabled) {
    return {
      code: "track_disabled",
      message: "Your microphone is muted in this page.",
      detail: "Use the microphone button to unmute.",
    };
  }
  // A *virtual* device is worth calling out by name. Loopback cables
  // (VB-Audio, VoiceMeeter, OBS, Steam) install themselves as the Windows
  // default input, so a machine that has one will silently hand the browser a
  // device carrying nothing — and it reports `live`, unmuted, with permission
  // granted. Exactly zero signal is the tell: a real microphone always has a
  // noise floor.
  const label = track.label || "unknown device";
  if (VIRTUAL_DEVICE_HINTS.some((hint) => label.toLowerCase().includes(hint))) {
    return {
      code: "no_signal",
      message: `Your browser is recording from "${label}", which is not a microphone.`,
      detail:
        "That is a virtual audio device and it is carrying no sound. Click the camera icon in " +
        "the address bar → Site settings → Microphone, and choose your real microphone. Speech " +
        "recognition follows the system default, so also set it in Windows Settings › System › " +
        "Sound › Input.",
    };
  }

  return {
    code: "no_signal",
    message: "Your microphone is open but no sound is arriving.",
    detail:
      `Recording from "${label}". If that is not the microphone you are speaking into, click the ` +
      "camera icon in the address bar → Site settings → Microphone and change it, then reload.",
  };
}

/** Substrings that mark an input as a loopback/virtual device rather than a
 * physical microphone. Matched case-insensitively against `track.label`. */
const VIRTUAL_DEVICE_HINTS = [
  "cable output",
  "vb-audio",
  "virtual cable",
  "voicemeeter",
  "virtual audio",
  "obs-",
  "stereo mix",
  "wave out mix",
  "what u hear",
];

export function useAudioLevel(stream: MediaStream | null, active: boolean): AudioLevelState {
  const [level, setLevel] = useState(0);
  const [silentForSeconds, setSilentForSeconds] = useState(0);
  const [peak, setPeak] = useState(0);
  const [diagnosis, setDiagnosis] = useState<AudioDiagnosis | null>(null);
  const silentSinceRef = useRef<number | null>(null);
  const peakRef = useRef(0);

  useEffect(() => {
    if (!stream || !active) {
      setLevel(0);
      silentSinceRef.current = null;
      setSilentForSeconds(0);
      setDiagnosis(null);
      peakRef.current = 0;
      setPeak(0);
      return;
    }

    const AudioContextCtor =
      window.AudioContext ??
      (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AudioContextCtor) return;

    const context = new AudioContextCtor();

    // **An AudioContext created outside a user gesture starts `suspended`, and
    // a suspended context's analyser returns silence forever.** Not an error,
    // not a warning — just an all-zero buffer, which is indistinguishable from
    // a muted microphone. This is what made the room report
    // `no_speech_detected` at a candidate who was talking: the meter was dead,
    // so every reading was silence.
    //
    // `resume()` is safe to call unconditionally and is a no-op on a context
    // that is already running.
    if (context.state === "suspended") {
      void context.resume().catch(() => undefined);
    }

    const source = context.createMediaStreamSource(stream);
    const analyser = context.createAnalyser();
    // Small window: this is a meter, not a spectrogram, and a large FFT costs
    // latency on every frame for resolution nothing reads.
    analyser.fftSize = 512;
    analyser.smoothingTimeConstant = 0.6;
    source.connect(analyser);

    // An analyser with no path to the destination is not guaranteed to be
    // pulled by the audio graph. A muted gain node gives it one without putting
    // a single sample of the candidate's own voice into their speakers — which
    // would be picked straight back up by the microphone.
    const sink = context.createGain();
    sink.gain.value = 0;
    analyser.connect(sink);
    sink.connect(context.destination);

    const samples = new Float32Array(analyser.fftSize);
    let frame = 0;
    let smoothed = 0;

    const tick = () => {
      analyser.getFloatTimeDomainData(samples);
      let sum = 0;
      for (let i = 0; i < samples.length; i += 1) sum += samples[i] * samples[i];
      const rms = Math.sqrt(sum / samples.length);

      // Asymmetric smoothing: rise quickly so the meter answers the moment
      // someone speaks, fall slowly so it does not strobe between syllables.
      smoothed = rms > smoothed ? rms : smoothed * 0.88 + rms * 0.12;
      const normalised = Math.min(1, smoothed * 6);
      setLevel(normalised);

      if (rms > peakRef.current) {
        peakRef.current = rms;
        setPeak(rms);
      }

      const now = performance.now();
      if (normalised > SILENCE_THRESHOLD) {
        silentSinceRef.current = null;
        setSilentForSeconds(0);
        setDiagnosis(null);
      } else {
        silentSinceRef.current ??= now;
        const seconds = Math.floor((now - silentSinceRef.current) / 1000);
        setSilentForSeconds(seconds);
        // Only after a grace period. Before that, silence is just a person who
        // has not started talking yet, and accusing their hardware of being
        // broken would be both rude and usually wrong.
        if (seconds >= DIAGNOSE_AFTER_SECONDS && peakRef.current <= SILENCE_THRESHOLD) {
          setDiagnosis(diagnose(context, stream));
        }
      }

      frame = requestAnimationFrame(tick);
    };

    frame = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(frame);
      source.disconnect();
      analyser.disconnect();
      sink.disconnect();
      void context.close();
    };
  }, [stream, active]);

  return { level, silent: level <= SILENCE_THRESHOLD, silentForSeconds, peak, diagnosis };
}
