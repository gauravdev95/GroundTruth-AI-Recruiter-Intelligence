import { isAxiosError } from "axios";
import { Loader2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import {
  useInterviewState,
  useLatestInterview,
  useLiveInterview,
} from "../../hooks/useInterview";
import { AiInterviewerStage } from "../components/AiInterviewerStage";
import { DeviceCheck } from "../components/DeviceCheck";
import { JoiningSequence } from "../components/JoiningSequence";
import {
  IntegrityLog,
  IntegrityNotice,
  RoomNotice,
  TypedAnswerBar,
} from "../components/RoomNotices";
import { RoomControlBar } from "../components/RoomControlBar";
import { RoomTopBar } from "../components/RoomTopBar";
import { SelfView } from "../components/SelfView";
import { TranscriptPanel } from "../components/TranscriptPanel";
import { useAudioLevel } from "../hooks/useAudioLevel";
import { useCameraObscured } from "../hooks/useCameraObscured";
import { useFullscreen } from "../hooks/useFullscreen";
import { useIntegrityMonitor } from "../hooks/useIntegrityMonitor";
import { useInterviewRoom } from "../hooks/useInterviewRoom";
import { useMediaDevices } from "../hooks/useMediaDevices";
import { detectSpeechSupport } from "../lib/speechCapabilities";
import "../styles/room.css";

/**
 * The interview room.
 *
 * ## What this page is, in one sentence
 *
 * A camera, a microphone, a speaking avatar and a full-screen dark layout
 * wrapped around `useLiveInterview` — the same hook, hitting the same socket
 * and the same `service.advance`, that the typed interview used.
 *
 * ## Why it is a separate route from `InterviewPage`
 *
 * `/student/interview/:projectId` lives inside `StudentDashboardLayout` and
 * shows the lobby before an interview and the evidence report after one. Those
 * both want a sidebar. A call does not — every pixel of navigation in an
 * interview room is a pixel inviting the candidate to leave mid-question — so
 * `/student/interview/:projectId/room` is declared as a sibling *outside* the
 * dashboard layout rather than as a child inside it. It is still behind
 * `ProtectedRoute` and `RequireProfileSetup`; it just does not mount a shell.
 *
 * This also means the room does not open the dashboard's realtime notification
 * socket, which would otherwise be free to pop a toast over an interview.
 *
 * ## The lifecycle
 *
 *   device check  →  joining  →  live  →  completed
 *                                    ↘  ended early  →  back to the lobby
 *
 * `joined` is the gate: nothing speaks, listens, or records an integrity event
 * before the candidate has pressed Join. A room that started transcribing on
 * page load would be recording somebody who had not agreed to be recorded.
 */

type RoomStage = "device_check" | "joining" | "live" | "finished";

export function InterviewRoomPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const rootRef = useRef<HTMLDivElement>(null);
  const selfVideoRef = useRef<HTMLVideoElement>(null);
  const previewVideoRef = useRef<HTMLVideoElement>(null);

  const [stage, setStage] = useState<RoomStage>("device_check");
  const [transcriptOpen, setTranscriptOpen] = useState(false);
  const [integrityOpen, setIntegrityOpen] = useState(false);

  const support = useMemo(() => detectSpeechSupport(), []);
  const media = useMediaDevices();
  const fullscreen = useFullscreen(rootRef);

  // -- the interview itself, unchanged ------------------------------------
  const latest = useLatestInterview(projectId ?? "");
  const interviewId = latest.data?.id ?? null;
  const query = useInterviewState(interviewId);
  const status = query.data?.interview.status;
  const joined = stage === "joining" || stage === "live";
  const live = useLiveInterview(interviewId, joined && status === "in_progress");

  // -- integrity ----------------------------------------------------------
  const elapsedSeconds = useCallback(() => {
    const limit = query.data?.interview.time_limit_seconds ?? 0;
    return Math.max(0, limit - live.timeRemaining);
  }, [query.data?.interview.time_limit_seconds, live.timeRemaining]);

  const integrity = useIntegrityMonitor({
    interviewId,
    active: stage === "live",
    elapsedSeconds,
  });

  const recordIntegrity = integrity.record;

  const audio = useAudioLevel(media.audioStream, joined && media.microphoneEnabled);
  const previewAudio = useAudioLevel(media.audioStream, stage === "device_check");
  const cameraObscured = useCameraObscured(selfVideoRef, stage === "live" && media.cameraEnabled);

  const room = useInterviewRoom({
    live,
    joined,
    onIntegrityEvent: recordIntegrity,
    microphoneSilentForSeconds: audio.silentForSeconds,
    microphoneEnabled: media.microphoneEnabled,
  });

  // Device-state signals. Each fires on the *transition*, so a camera that is
  // off for five minutes is one event rather than one per render.
  useEffect(() => {
    if (stage !== "live") return;
    if (media.cameraLost) recordIntegrity("camera_unavailable");
  }, [media.cameraLost, stage, recordIntegrity]);

  useEffect(() => {
    if (stage !== "live") return;
    if (media.microphoneLost) recordIntegrity("microphone_unavailable");
  }, [media.microphoneLost, stage, recordIntegrity]);

  useEffect(() => {
    if (stage !== "live" || media.cameraEnabled) return;
    recordIntegrity("camera_disabled");
  }, [media.cameraEnabled, stage, recordIntegrity]);

  useEffect(() => {
    if (stage !== "live" || media.microphoneEnabled) return;
    recordIntegrity("microphone_disabled");
  }, [media.microphoneEnabled, stage, recordIntegrity]);

  useEffect(() => {
    if (stage !== "live" || !cameraObscured) return;
    recordIntegrity("camera_obscured");
  }, [cameraObscured, stage, recordIntegrity]);

  // -- stage transitions --------------------------------------------------
  useEffect(() => {
    // The interviewer has spoken: the room is live. Driven by the transcript
    // rather than by a timer, so "joining" lasts exactly as long as joining
    // actually takes.
    if (stage === "joining" && live.transcript.length > 0) setStage("live");
  }, [stage, live.transcript.length]);

  useEffect(() => {
    if (status === "evaluating" || status === "completed" || status === "failed") {
      setStage((current) => (current === "device_check" ? current : "finished"));
    }
  }, [status]);

  // Release the camera the moment the interview is over. Holding a device open
  // on a finished interview leaves the browser's recording indicator lit at
  // somebody who is no longer being interviewed.
  //
  // Depends on the two stable callbacks rather than on `media` and `integrity`,
  // which are fresh objects every render — depending on those would re-run this
  // on every render for as long as the room sat on the finished screen.
  const releaseMedia = media.release;
  const flushIntegrity = integrity.flush;

  useEffect(() => {
    if (stage !== "finished") return;
    releaseMedia();
    flushIntegrity();
  }, [stage, releaseMedia, flushIntegrity]);

  const join = useCallback(() => {
    setStage("joining");
    // Tied to this click, which is what makes the browser grant it — see
    // `useFullscreen`. A refusal is fine and changes nothing about the layout.
    void fullscreen.enter();
  }, [fullscreen]);

  const exitFullscreen = fullscreen.exit;

  const leave = useCallback(() => {
    flushIntegrity();
    releaseMedia();
    void exitFullscreen();
    navigate(`/student/interview/${projectId}`);
  }, [flushIntegrity, releaseMedia, exitFullscreen, navigate, projectId]);

  // Warn before an accidental close. Only while live — a beforeunload prompt on
  // the report screen is just an annoyance.
  useEffect(() => {
    if (stage !== "live") return;
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [stage]);

  if (!projectId) return null;

  // -- pre-join -----------------------------------------------------------
  const interviewMissing =
    latest.isError && isAxiosError(latest.error) && latest.error.response?.status === 404;

  if (interviewMissing || latest.data?.status === "failed") {
    // Nothing to join. The lobby owns starting an interview; sending them there
    // rather than duplicating the start button keeps one entry point.
    return <Redirecting to={`/student/interview/${projectId}`} navigate={navigate} />;
  }

  const shell = (children: React.ReactNode) => (
    <div
      ref={rootRef}
      data-interview-room
      className="fixed inset-0 z-50 flex flex-col overflow-hidden bg-[var(--room-floor)] text-[var(--room-ink)]"
    >
      {children}
    </div>
  );

  if (latest.isPending || !interviewId) {
    return shell(
      <div className="flex h-full items-center justify-center">
        <Loader2 size={22} className="animate-spin text-[var(--room-slate)]" aria-hidden="true" />
      </div>,
    );
  }

  if (stage === "device_check") {
    return shell(
      <div className="h-full overflow-y-auto">
        <DeviceCheck
          projectTitle={query.data?.interview.project_id ? "your repository" : "your profile"}
          camera={media.camera}
          microphone={media.microphone}
          stream={media.stream}
          videoRef={previewVideoRef}
          level={previewAudio.level}
          peak={previewAudio.peak}
          audioDiagnosis={previewAudio.diagnosis}
          audioDeviceLabel={media.audioDeviceLabel}
          support={support}
          interviewReady={status === "in_progress"}
          error={media.error}
          onRequestDevices={() => void media.request()}
          onJoin={join}
          onCancel={() => navigate(`/student/interview/${projectId}`)}
        />
      </div>,
    );
  }

  if (stage === "finished") {
    return shell(
      <div className="flex h-full flex-col items-center justify-center gap-4 px-6 text-center">
        <p className="font-display text-xl font-semibold">That&apos;s everything — thank you.</p>
        <p className="max-w-md text-sm leading-relaxed text-[var(--room-slate)]">
          {status === "failed"
            ? "This attempt ran into a problem. You can see what happened on the interview page."
            : "Your conversation is being reviewed against the same repository analysis the questions came from. Your report will be ready in a moment."}
        </p>
        <button
          type="button"
          onClick={leave}
          className="mt-2 rounded-[var(--r-md)] bg-[var(--room-accent)] px-6 py-2.5 text-sm font-semibold text-[#04060f] transition-[filter] hover:brightness-110"
        >
          Leave the room
        </button>
      </div>,
    );
  }

  // -- live ---------------------------------------------------------------
  const awaitingCandidate = live.state?.awaiting_candidate ?? false;
  // `speechError` belongs in this condition, and leaving it out was the failure
  // that stranded a candidate completely: the recogniser can fail *at runtime*
  // (an unreachable speech service, a device grabbed by another app) on a
  // browser that supports it perfectly well, with the microphone enabled. Both
  // other flags stayed false, so no typed bar was offered — and the only way to
  // answer an interview question had silently gone away with nothing on screen
  // to replace it.
  const typedMode = !room.speechSupported || !media.microphoneEnabled || room.speechError !== null;

  return shell(
    <>
      <RoomTopBar
        title="Technical interview"
        timeRemaining={live.timeRemaining}
        connection={live.connection}
        integrityCount={Object.values(integrity.counts).reduce<number>(
          (total, count) => total + (count ?? 0),
          0,
        )}
        onOpenIntegrity={() => setIntegrityOpen((open) => !open)}
      />

      <div className="relative flex min-h-0 flex-1">
        <main className="relative min-w-0 flex-1">
          {stage === "joining" ? (
            <JoiningSequence
              cameraReady={media.camera === "granted"}
              microphoneReady={media.microphone === "granted"}
              interviewerReady={live.transcript.length > 0}
            />
          ) : (
            <AiInterviewerStage
              phase={room.phase}
              speaking={room.interviewerSpeaking}
              caption={room.currentUtterance}
              candidateSpeaking={room.candidateSpeaking}
              muted={room.muted}
            />
          )}

          {/* Self-view, pinned. Bottom-right on desktop, and above the typed
              composer when there is one so it never covers the control the
              candidate is trying to use. */}
          <div
            className="absolute right-4 z-10 sm:right-6"
            style={{ bottom: typedMode ? "5.5rem" : "1.5rem" }}
          >
            <SelfView
              stream={media.stream}
              videoRef={selfVideoRef}
              cameraEnabled={media.cameraEnabled}
              microphoneEnabled={media.microphoneEnabled}
              cameraLost={media.cameraLost}
              level={audio.level}
              label="You"
            />
          </div>

          {/* Notices, stacked top-centre and out of the way of both faces. */}
          <div className="pointer-events-none absolute inset-x-0 top-4 z-20 mx-auto flex w-full max-w-lg flex-col items-center gap-2 px-4">
            <IntegrityNotice warning={integrity.warning} onDismiss={integrity.dismissWarning} />

            {live.connection === "reconnecting" ? (
              <RoomNotice
                tone="warning"
                title="Connection lost"
                description="Reconnecting — nothing you've said is lost."
              />
            ) : null}

            {live.connection === "unavailable" ? (
              <RoomNotice
                tone="warning"
                title="Live connection unavailable"
                description="Your answers are still being sent, just without the live indicator."
              />
            ) : null}

            {media.cameraLost ? (
              <RoomNotice
                tone="warning"
                title="Camera stopped"
                description="Check nothing else is using it. The interview continues without video."
                action={{ label: "Retry", onClick: () => void media.request() }}
              />
            ) : null}

            {media.microphoneLost ? (
              <RoomNotice
                tone="warning"
                title="Microphone stopped"
                description="Reconnect it to keep speaking, or type your answer instead."
                action={{ label: "Retry", onClick: () => void media.request() }}
              />
            ) : null}

            {/* The recogniser's own words, not a generic line. A candidate
                whose speech service is unreachable used to be told only that
                there was "a problem" — while the room kept showing
                "Listening", which was a lie it had no way to notice. */}
            {room.speechError ? (
              <RoomNotice
                tone="warning"
                title="The microphone isn't being heard"
                description={room.speechError}
              />
            ) : null}

            {live.pending?.failed ? (
              <RoomNotice
                tone="warning"
                title="That answer didn't send"
                description="Say it again, or type it — nothing before it was affected."
              />
            ) : null}

            {!fullscreen.active && fullscreen.supported ? (
              <RoomNotice
                tone="info"
                title="You've left full screen"
                description="The interview is still running."
                action={{ label: "Full screen", onClick: () => void fullscreen.enter() }}
              />
            ) : null}

            <IntegrityLog
              open={integrityOpen}
              counts={integrity.counts}
              onClose={() => setIntegrityOpen(false)}
            />
          </div>

          {/* The typed path, when there is no recogniser or the candidate has
              muted themselves. Not a chat window — one line, in the room. */}
          {typedMode && stage === "live" ? (
            <div className="pointer-events-none absolute inset-x-0 bottom-5 z-10 flex justify-center px-4">
              <TypedAnswerBar
                enabled={awaitingCandidate && !live.isThinking}
                placeholder={
                  !awaitingCandidate
                    ? "Wait for the interviewer…"
                    : room.speechError !== null
                      ? "Speech isn't working — type your answer…"
                      : !media.microphoneEnabled
                        ? "Your microphone is muted — type your answer…"
                        : "Type your answer…"
                }
                onSubmit={room.submitTyped}
              />
            </div>
          ) : null}
        </main>

        <TranscriptPanel
          open={transcriptOpen}
          transcript={live.transcript}
          interim={room.interim}
          onClose={() => setTranscriptOpen(false)}
        />
      </div>

      <RoomControlBar
        microphoneEnabled={media.microphoneEnabled}
        cameraEnabled={media.cameraEnabled}
        speakerMuted={room.muted}
        transcriptOpen={transcriptOpen}
        fullscreenActive={fullscreen.active}
        fullscreenSupported={fullscreen.supported}
        canFinishAnswering={room.listening && room.candidateSpeaking}
        onFinishAnswering={room.finishAnswering}
        onToggleMicrophone={() => media.setMicrophoneEnabled(!media.microphoneEnabled)}
        onToggleCamera={() => media.setCameraEnabled(!media.cameraEnabled)}
        onToggleSpeaker={() => room.setMuted(!room.muted)}
        onToggleTranscript={() => setTranscriptOpen((open) => !open)}
        onReplayLast={room.replayLast}
        onEnterFullscreen={() => void fullscreen.enter()}
        onEnd={leave}
      />
    </>,
  );
}

/** A redirect that runs as an effect rather than during render, so it cannot
 * fire while React is still committing the tree that asked for it. */
function Redirecting({
  to,
  navigate,
}: {
  to: string;
  navigate: ReturnType<typeof useNavigate>;
}) {
  useEffect(() => {
    navigate(to, { replace: true });
  }, [to, navigate]);
  return null;
}
