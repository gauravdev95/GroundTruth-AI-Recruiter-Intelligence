import { AlertTriangle, Check, Loader2, Mic, MicOff, Video, VideoOff } from "lucide-react";
import { useEffect, type RefObject } from "react";

import type { AudioDiagnosis } from "../hooks/useAudioLevel";
import type { PermissionState } from "../hooks/useMediaDevices";
import type { SpeechSupport } from "../lib/speechCapabilities";

/**
 * The green room.
 *
 * Every video product puts one of these in front of a call, and the reason is
 * not politeness: a candidate who discovers their microphone is dead *during*
 * an assessment has already lost part of the assessment. This screen exists so
 * that the first thing anyone says in the interview is not "can you hear me?".
 *
 * ## It is also where consent is asked for, in words
 *
 * The brief's privacy requirement is that the candidate is told what is
 * collected. That belongs here — before a device is opened, not in a policy
 * page afterwards — and it has to be specific enough to be true:
 *
 * - the camera preview is local and never uploaded or recorded;
 * - the microphone is transcribed to text, and on this browser that
 *   transcription happens at Google (see `lib/speechCapabilities.ts`), which is
 *   a third party hearing their voice and must be said out loud;
 * - only the text reaches GroundTruth;
 * - session conditions (tab switches, device state) are recorded separately.
 *
 * ## Joining is possible without a camera, and not without a microphone
 *
 * ...unless the browser has no recogniser at all, in which case the interview
 * is typed and neither device is required. The button's enabled state encodes
 * exactly that rule and the copy underneath it says which case the candidate is
 * in, because "Join" being greyed out with no explanation is the worst possible
 * thing to show somebody about to be interviewed.
 */

interface DeviceRowProps {
  icon: React.ReactNode;
  offIcon: React.ReactNode;
  label: string;
  state: PermissionState;
  hint: string;
  /** The device actually in use. Shown even when everything is fine. */
  note?: string | null;
}

const STATE_COPY: Record<PermissionState, { text: string; tone: string }> = {
  idle: { text: "Not checked", tone: "text-[var(--room-muted)]" },
  prompting: { text: "Waiting for permission…", tone: "text-[var(--room-slate)]" },
  granted: { text: "Ready", tone: "text-[var(--room-accent)]" },
  denied: { text: "Permission declined", tone: "text-[var(--room-danger)]" },
  unavailable: { text: "Unavailable", tone: "text-[var(--room-caution)]" },
};

function DeviceRow({ icon, offIcon, label, state, hint, note }: DeviceRowProps) {
  const copy = STATE_COPY[state];
  const ok = state === "granted";

  return (
    <div className="flex items-start gap-3 rounded-[var(--r-md)] border border-[var(--room-rule)] bg-[var(--room-panel)] px-4 py-3">
      <span className={ok ? "text-[var(--room-accent)]" : "text-[var(--room-muted)]"}>
        {ok ? icon : offIcon}
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-[var(--room-ink)]">{label}</p>
        <p className={["mt-0.5 text-xs", copy.tone].join(" ")}>{copy.text}</p>
        {note ? (
          <p className="machine mt-1 truncate text-[11px] text-[var(--room-muted)]" title={note}>
            {note}
          </p>
        ) : null}
        {!ok && state !== "idle" && state !== "prompting" ? (
          <p className="mt-1 text-xs leading-relaxed text-[var(--room-muted)]">{hint}</p>
        ) : null}
      </div>
      {state === "prompting" ? (
        <Loader2 size={16} className="animate-spin text-[var(--room-slate)]" aria-hidden="true" />
      ) : ok ? (
        <Check size={16} className="text-[var(--room-accent)]" aria-hidden="true" />
      ) : (
        <AlertTriangle size={16} className="text-[var(--room-caution)]" aria-hidden="true" />
      )}
    </div>
  );
}

export interface DeviceCheckProps {
  projectTitle: string;
  camera: PermissionState;
  microphone: PermissionState;
  stream: MediaStream | null;
  videoRef: RefObject<HTMLVideoElement>;
  level: number;
  /** Loudest sample since the microphone opened. Drives the "we have heard you"
   * confirmation — the instantaneous level cannot say that, because it is zero
   * again the moment someone stops talking. */
  peak: number;
  /** Set when the microphone is granted but silent for long enough that
   * something is actually wrong. Rendered verbatim: a candidate cannot fix a
   * fault nobody names. */
  audioDiagnosis: AudioDiagnosis | null;
  /** Which input the browser actually opened. Shown plainly, always — a
   * candidate who can see "CABLE Output (VB-Audio Virtual Cable)" under
   * "Microphone: Ready" can fix it in seconds; one who cannot has no way to
   * even suspect it. */
  audioDeviceLabel: string | null;
  support: SpeechSupport;
  /** True once questions exist server-side. Until then the room can be prepared
   * but not entered — see `InterviewStatus.PENDING`. */
  interviewReady: boolean;
  error: string | null;
  onRequestDevices: () => void;
  onJoin: () => void;
  onCancel: () => void;
}

export function DeviceCheck({
  projectTitle,
  camera,
  microphone,
  stream,
  videoRef,
  level,
  peak,
  audioDiagnosis,
  audioDeviceLabel,
  support,
  interviewReady,
  error,
  onRequestDevices,
  onJoin,
  onCancel,
}: DeviceCheckProps) {
  useEffect(() => {
    const element = videoRef.current;
    if (element && element.srcObject !== stream) element.srcObject = stream;
  }, [stream, videoRef]);

  // Voice needs a microphone. Typed does not need anything. Encoding the rule
  // once, here, is what keeps the button and the explanation from disagreeing.
  const voiceInterview = support.recognition;
  const canJoin = interviewReady && (!voiceInterview || microphone === "granted");

  const blockedReason = !interviewReady
    ? "Your interviewer is still reading your repository."
    : voiceInterview && microphone !== "granted"
      ? "A microphone is required for the voice interview."
      : null;

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-8 px-6 py-10">
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-[var(--room-muted)]">
          Interview room
        </p>
        <h1 className="mt-1.5 font-display text-2xl font-semibold text-[var(--room-ink)]">
          Ready to join?
        </h1>
        <p className="mt-2 max-w-xl text-sm leading-relaxed text-[var(--room-slate)]">
          A live technical conversation about <span className="text-[var(--room-ink)]">{projectTitle}</span> with
          an interviewer that has already read the code. Check your camera and microphone before you
          go in.
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-[1.1fr_1fr]">
        <div
          className="relative overflow-hidden rounded-[var(--r-lg)] border border-[var(--room-rule-strong)] bg-[var(--room-stage)]"
          style={{ aspectRatio: "4 / 3" }}
        >
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className="h-full w-full object-cover"
            style={{ transform: "scaleX(-1)", opacity: camera === "granted" ? 1 : 0 }}
          />
          {camera !== "granted" ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-[var(--room-muted)]">
              <VideoOff size={26} aria-hidden="true" />
              <p className="text-xs">No camera preview</p>
            </div>
          ) : null}

          {/* The level meter here answers "is it hearing me" before the
              interview rather than during it. */}
          {microphone === "granted" ? (
            <div className="absolute inset-x-3 bottom-3 flex items-center gap-2 rounded-full bg-[rgb(4_6_15/0.7)] px-3 py-2 backdrop-blur-sm">
              <Mic size={13} className="shrink-0 text-[var(--room-accent)]" aria-hidden="true" />
              <span className="h-1 flex-1 overflow-hidden rounded-full bg-[var(--room-rule-strong)]">
                <span
                  className="block h-full rounded-full bg-[var(--room-accent)] transition-[width] duration-100"
                  style={{ width: `${Math.round(level * 100)}%` }}
                />
              </span>
              <span
                className="shrink-0 text-[10px]"
                style={{ color: peak > 0.02 ? "var(--room-accent)" : "var(--room-slate)" }}
              >
                {peak > 0.02 ? "Heard you" : "Say something"}
              </span>
            </div>
          ) : null}
        </div>

        <div className="flex flex-col gap-3">
          <DeviceRow
            icon={<Mic size={18} />}
            offIcon={<MicOff size={18} />}
            label="Microphone"
            state={microphone}
            hint="Allow microphone access in your browser's address bar, then check again."
            note={microphone === "granted" ? audioDeviceLabel : null}
          />
          <DeviceRow
            icon={<Video size={18} />}
            offIcon={<VideoOff size={18} />}
            label="Camera"
            state={camera}
            hint="You can take the interview without a camera. Your interviewer is audio only either way."
          />

          {camera === "idle" || microphone === "idle" || camera === "denied" || microphone === "denied" ? (
            <button
              type="button"
              onClick={onRequestDevices}
              className="rounded-[var(--r-md)] border border-[var(--room-rule-strong)] bg-[var(--room-raised)] px-4 py-2.5 text-sm font-medium text-[var(--room-ink)] transition-colors hover:bg-[rgb(30_40_64/1)]"
            >
              {camera === "idle" && microphone === "idle" ? "Check my devices" : "Check again"}
            </button>
          ) : null}

          {audioDiagnosis ? (
            <div className="rounded-[var(--r-md)] border border-[rgb(244_86_79/0.35)] bg-[var(--room-danger-dim)] px-3 py-2.5">
              <p className="text-xs font-medium text-[var(--room-ink)]">{audioDiagnosis.message}</p>
              <p className="mt-1 text-xs leading-relaxed text-[var(--room-slate)]">
                {audioDiagnosis.detail}
              </p>
            </div>
          ) : null}

          {!support.recognition ? (
            <p className="rounded-[var(--r-md)] border border-[rgb(255_180_84/0.3)] bg-[var(--room-caution-dim)] px-3 py-2.5 text-xs leading-relaxed text-[var(--room-ink)]">
              This browser can&apos;t transcribe speech, so you&apos;ll type your answers instead.
              Everything else works the same. For the spoken interview, use Chrome or Edge.
            </p>
          ) : null}

          {!support.synthesis ? (
            <p className="rounded-[var(--r-md)] border border-[rgb(255_180_84/0.3)] bg-[var(--room-caution-dim)] px-3 py-2.5 text-xs leading-relaxed text-[var(--room-ink)]">
              This browser has no speech output, so you&apos;ll read the interviewer&apos;s questions
              rather than hear them.
            </p>
          ) : null}

          {error ? (
            <p role="alert" className="text-xs leading-relaxed text-[var(--room-danger)]">
              {error}
            </p>
          ) : null}
        </div>
      </div>

      {/* Consent, in specifics. See the component docstring for why this is
          here and not in a policy link. */}
      <div className="rounded-[var(--r-md)] border border-[var(--room-rule)] bg-[var(--room-panel)] px-4 py-3.5">
        <p className="text-xs font-medium text-[var(--room-ink)]">What happens to your camera and microphone</p>
        <ul className="mt-2 space-y-1.5 text-xs leading-relaxed text-[var(--room-slate)]">
          <li>
            Your video stays on this device. Nothing is recorded and no frame is ever uploaded.
          </li>
          <li>
            Your speech is turned into text{support.recognition ? " by your browser's speech service" : ""}.
            Only that text is sent to GroundTruth, and only that text is scored.
          </li>
          <li>
            Session conditions — tab switches, whether a device stopped — are recorded separately
            from your answers and are not part of your score.
          </li>
        </ul>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={onJoin}
          disabled={!canJoin}
          className="rounded-[var(--r-md)] bg-[var(--room-accent)] px-6 py-2.5 text-sm font-semibold text-[#04060f] transition-[filter] hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {interviewReady ? "Join interview" : "Preparing…"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-[var(--r-md)] px-4 py-2.5 text-sm text-[var(--room-slate)] transition-colors hover:text-[var(--room-ink)]"
        >
          Not now
        </button>
        {blockedReason ? (
          <p className="text-xs text-[var(--room-muted)]">{blockedReason}</p>
        ) : (
          <p className="text-xs text-[var(--room-muted)]">
            You can only take this interview once for this repository.
          </p>
        )}
      </div>
    </div>
  );
}
