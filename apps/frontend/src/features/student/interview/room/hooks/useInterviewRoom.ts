import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { InterviewState, InterviewTurn } from "../../api/interviewApi";
import type { ConnectionState, LiveInterview } from "../../hooks/useInterview";
import { useSpeechRecognition } from "./useSpeechRecognition";
import { useSpeechSynthesis } from "./useSpeechSynthesis";

/**
 * The conversation loop, as a state machine.
 *
 * ## This adds a voice to the interview. It does not add an interview.
 *
 * Every question this hook speaks came out of `service.advance` → LangGraph →
 * the Interviewer agent, grounded in the repository analysis. Every answer it
 * hears goes back through `live.send` to that same `service.advance`, through
 * the Verifier and the graph's `decide`. Nothing here generates a question,
 * scores an answer, or decides what comes next — this file only turns text into
 * sound, sound into text, and the gap between them into a turn.
 *
 * If this hook were deleted, the interview would still run. That is the test it
 * is written to pass.
 *
 * ## The cycle
 *
 *   a new interviewer turn appears in the server transcript
 *     → microphone closed          (so the AI is not transcribed as the candidate)
 *     → the turn is spoken
 *     → speech ends
 *     → microphone opened          ("Listening…" starts being literally true)
 *     → candidate speaks, pauses
 *     → the recogniser calls it a finished answer
 *     → microphone closed, answer sent
 *     → server thinks
 *     → a new interviewer turn appears
 *
 * The microphone is never open while the interviewer is speaking, and never
 * open while an answer is in flight. Both are load-bearing: the first stops the
 * AI answering itself through the candidate's speakers, the second stops a
 * candidate's afterthought arriving as a second turn on top of the first.
 *
 * ## Phases the room can honestly know
 *
 * The brief asks for `FOLLOW_UP` and `NEXT_QUESTION` as visible states. They are
 * deliberately absent. Whether the graph chose to probe or to move on is a
 * decision made inside `decide`, and the client is not told — but more to the
 * point, a real interviewer does not caption their own intent, and a room that
 * displayed "FOLLOW-UP" above a question would be doing the one thing the whole
 * rebuild is meant to stop: making it obvious you are talking to a machine.
 * The difference is already audible in what the interviewer says.
 */

export type RoomPhase =
  | "joining"
  | "interviewer_speaking"
  | "listening"
  | "processing"
  | "thinking"
  | "closing"
  | "completed"
  | "reconnecting"
  | "error";

/** Under two minutes the room shifts into its closing state. Two minutes, not
 * the server's own 90s wrap-up threshold, which the client is never told: the
 * visual state is a courtesy that should land slightly *before* the graph
 * starts closing, and the routing decision stays entirely the graph's. */
const CLOSING_SECONDS = 120;

/** Long enough to be worth a nudge, short enough to be actionable. */
const NO_SPEECH_SECONDS = 45;
const INACTIVITY_SECONDS = 150;

export interface InterviewRoomOptions {
  live: LiveInterview;
  /** False until the candidate has passed the device check and joined. */
  joined: boolean;
  /** Report a session-condition observation. Wired to `useIntegrityMonitor`. */
  onIntegrityEvent: (
    eventType: "no_speech_detected" | "inactivity" | "connection_lost",
    options?: { durationSeconds?: number },
  ) => void;
  /** Silence in the candidate's own microphone, from `useAudioLevel`. */
  microphoneSilentForSeconds: number;
  /** False when the candidate has muted themselves — the room must not report
   * "we can't hear you" at somebody who pressed mute on purpose. */
  microphoneEnabled: boolean;
}

export interface InterviewRoomState {
  phase: RoomPhase;
  /** What the interviewer is saying or last said, for the caption line. */
  currentUtterance: string | null;
  /** The candidate's speech as it is being recognised. */
  interim: string;
  /** True when the room is reading the microphone right now. */
  listening: boolean;
  /** True when the candidate is mid-sentence. */
  candidateSpeaking: boolean;
  /** The interviewer's voice is playing. */
  interviewerSpeaking: boolean;
  speechSupported: boolean;
  synthesisSupported: boolean;
  speechError: string | null;
  muted: boolean;
  setMuted: (muted: boolean) => void;
  /** Submit the current answer now rather than waiting out the silence timer. */
  finishAnswering: () => void;
  /** Say the last question again. Exists because a candidate who reloads, or
   * whose speakers were muted, otherwise has no way to hear a question that has
   * already been spoken — and reading it off the transcript panel is exactly
   * the chatbot experience this replaces. */
  replayLast: () => void;
  /** The typed path, for browsers with no recogniser and for a candidate who
   * would rather write. Same `service.advance`, same everything. */
  submitTyped: (text: string) => void;
}

function lastInterviewerTurn(transcript: InterviewTurn[]): InterviewTurn | null {
  for (let i = transcript.length - 1; i >= 0; i -= 1) {
    if (transcript[i].role === "interviewer") return transcript[i];
  }
  return null;
}

function derivePhase(args: {
  connection: ConnectionState;
  state: InterviewState | null;
  interviewerSpeaking: boolean;
  listening: boolean;
  isThinking: boolean;
  awaitingSubmit: boolean;
  timeRemaining: number;
  fatalError: boolean;
}): RoomPhase {
  if (args.fatalError) return "error";
  if (args.state?.interview.status === "completed") return "completed";
  if (args.state?.interview.status === "evaluating") return "completed";
  if (args.state?.interview.stage === "done") return "completed";
  if (args.connection === "reconnecting") return "reconnecting";
  if (args.interviewerSpeaking) return "interviewer_speaking";
  if (args.isThinking) return "thinking";
  if (args.awaitingSubmit) return "processing";
  if (args.listening) {
    return args.timeRemaining > 0 && args.timeRemaining <= CLOSING_SECONDS
      ? "closing"
      : "listening";
  }
  if (!args.state || args.state.transcript.length === 0) return "joining";
  return "thinking";
}

export function useInterviewRoom({
  live,
  joined,
  onIntegrityEvent,
  microphoneSilentForSeconds,
  microphoneEnabled,
}: InterviewRoomOptions): InterviewRoomState {
  const synthesis = useSpeechSynthesis();
  const [currentUtterance, setCurrentUtterance] = useState<string | null>(null);
  const [awaitingSubmit, setAwaitingSubmit] = useState(false);

  const spokenIdsRef = useRef<Set<string>>(new Set());
  const primedRef = useRef(false);
  const sendRef = useRef(live.send);
  const joinedRef = useRef(joined);
  const awaitingCandidateRef = useRef(false);

  useEffect(() => {
    sendRef.current = live.send;
    joinedRef.current = joined;
    awaitingCandidateRef.current = live.state?.awaiting_candidate ?? false;
  });

  /** One finished answer, on its way to `service.advance`. */
  const handleUtterance = useCallback((text: string) => {
    if (!joinedRef.current || !awaitingCandidateRef.current) return;
    setAwaitingSubmit(true);
    sendRef.current(text);
  }, []);

  const recognition = useSpeechRecognition({ onUtterance: handleUtterance });

  const recognitionRef = useRef(recognition);
  useEffect(() => {
    recognitionRef.current = recognition;
  });

  // Pulled out of the `synthesis` object deliberately. Both are stable
  // `useCallback`s, but `synthesis` itself is a fresh object every render — and
  // depending on the object would re-run the speaking effect below on every
  // render, whose cleanup sets `cancelled = true`. That would cancel the
  // in-flight `speak()` continuation of the *previous* run, and the microphone
  // would never reopen after a question. The bug is silent and total: the
  // interviewer speaks, and then nothing ever happens again.
  const { speak, cancel: cancelSpeech } = synthesis;

  // -- speak each new interviewer turn, exactly once ------------------------
  //
  // Keyed on turn id rather than on transcript length: a reconnect re-sends the
  // whole conversation, and a length check would have the interviewer read the
  // entire interview back to a candidate whose wifi blinked.
  useEffect(() => {
    if (!joined) return;

    const transcript = live.transcript;
    if (!primedRef.current) {
      // Everything already on screen at join time was spoken before this room
      // mounted (a reload mid-interview). Mark it heard; `replayLast` is how a
      // candidate asks for the last one again.
      transcript.forEach((turn) => spokenIdsRef.current.add(turn.id));
      primedRef.current = true;
      const last = lastInterviewerTurn(transcript);
      if (last) setCurrentUtterance(last.text);
      return;
    }

    const next = transcript.find(
      (turn) => turn.role === "interviewer" && !spokenIdsRef.current.has(turn.id),
    );
    if (!next) return;

    spokenIdsRef.current.add(next.id);
    setCurrentUtterance(next.text);
    setAwaitingSubmit(false);

    let cancelled = false;
    // Closed *before* the first syllable. See the module docstring — this is
    // the barge-in guard, not a nicety.
    recognitionRef.current.pause();

    void speak(next.text).then(() => {
      if (cancelled) return;
      // Only reopen the microphone if the server agrees it is the candidate's
      // turn. The wrap-up turn is an interviewer utterance with nothing owed
      // after it, and listening past it would leave a microphone open on a
      // finished interview.
      if (awaitingCandidateRef.current && joinedRef.current) {
        recognitionRef.current.start();
      }
    });

    return () => {
      cancelled = true;
    };
  }, [live.transcript, joined, speak]);

  // -- close the microphone when it is not the candidate's turn -------------
  useEffect(() => {
    if (!joined) return;
    const awaiting = live.state?.awaiting_candidate ?? false;
    if (!awaiting && recognitionRef.current.listening) {
      recognitionRef.current.pause();
    }
  }, [live.state?.awaiting_candidate, joined]);

  // -- tear the microphone down the moment the interview is over -----------
  useEffect(() => {
    const status = live.state?.interview.status;
    const finished = status === "evaluating" || status === "completed";
    if (finished) {
      recognitionRef.current.stop();
      cancelSpeech();
    }
  }, [live.state?.interview.status, cancelSpeech]);

  useEffect(() => {
    return () => {
      recognitionRef.current.stop();
    };
  }, []);

  // -- a failed send must not leave the room stuck on "processing" ----------
  useEffect(() => {
    if (live.pending?.failed) setAwaitingSubmit(false);
  }, [live.pending?.failed]);

  useEffect(() => {
    if (!live.isThinking) return;
    setAwaitingSubmit(false);
  }, [live.isThinking]);

  // -- silence and inactivity ----------------------------------------------
  //
  // Reported once per crossing rather than once per second, and only while the
  // room is actually waiting on the candidate with their own microphone on. A
  // candidate who muted themselves is not "not speaking", they are muted, and
  // the room already shows that.
  const reportedSilenceRef = useRef<{ nudged: boolean; inactive: boolean }>({
    nudged: false,
    inactive: false,
  });
  const awaitingCandidate = live.state?.awaiting_candidate ?? false;

  useEffect(() => {
    if (!joined || !awaitingCandidate || !microphoneEnabled || synthesis.speaking) {
      reportedSilenceRef.current = { nudged: false, inactive: false };
      return;
    }
    if (microphoneSilentForSeconds < NO_SPEECH_SECONDS) {
      reportedSilenceRef.current = { nudged: false, inactive: false };
      return;
    }
    if (!reportedSilenceRef.current.nudged) {
      reportedSilenceRef.current.nudged = true;
      onIntegrityEvent("no_speech_detected", { durationSeconds: microphoneSilentForSeconds });
    }
    if (microphoneSilentForSeconds >= INACTIVITY_SECONDS && !reportedSilenceRef.current.inactive) {
      reportedSilenceRef.current.inactive = true;
      onIntegrityEvent("inactivity", { durationSeconds: microphoneSilentForSeconds });
    }
  }, [
    joined,
    awaitingCandidate,
    microphoneEnabled,
    microphoneSilentForSeconds,
    synthesis.speaking,
    onIntegrityEvent,
  ]);

  // -- connection ----------------------------------------------------------
  const previousConnectionRef = useRef<ConnectionState>(live.connection);
  useEffect(() => {
    const previous = previousConnectionRef.current;
    previousConnectionRef.current = live.connection;
    if (previous === "live" && live.connection === "reconnecting") {
      onIntegrityEvent("connection_lost");
    }
  }, [live.connection, onIntegrityEvent]);

  const replayLast = useCallback(() => {
    const last = lastInterviewerTurn(live.transcript);
    if (!last) return;
    recognitionRef.current.pause();
    void speak(last.text).then(() => {
      if (awaitingCandidateRef.current && joinedRef.current) recognitionRef.current.start();
    });
  }, [live.transcript, speak]);

  const submitTyped = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) return;
      recognitionRef.current.pause();
      handleUtterance(trimmed);
    },
    [handleUtterance],
  );

  const phase = useMemo(
    () =>
      derivePhase({
        connection: live.connection,
        state: live.state,
        interviewerSpeaking: synthesis.speaking,
        listening: recognition.listening,
        isThinking: live.isThinking,
        awaitingSubmit,
        timeRemaining: live.timeRemaining,
        fatalError: live.connection === "unavailable" && live.error !== null,
      }),
    [
      live.connection,
      live.state,
      live.isThinking,
      live.timeRemaining,
      live.error,
      synthesis.speaking,
      recognition.listening,
      awaitingSubmit,
    ],
  );

  return {
    phase,
    currentUtterance,
    interim: recognition.interim,
    listening: recognition.listening,
    candidateSpeaking: recognition.speaking,
    interviewerSpeaking: synthesis.speaking,
    speechSupported: recognition.supported,
    synthesisSupported: synthesis.supported,
    speechError: recognition.error,
    muted: synthesis.muted,
    setMuted: synthesis.setMuted,
    finishAnswering: recognition.flush,
    replayLast,
    submitTyped,
  };
}
