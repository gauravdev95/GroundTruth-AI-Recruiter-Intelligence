import { Clock } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components";

import type { InterviewQuestion } from "../api/interviewApi";

interface TimedQuestionProps {
  question: InterviewQuestion;
  questionNumber: number;
  totalQuestions: number;
  isSubmitting: boolean;
  onSubmit: (transcript: string, timeTakenSeconds: number) => void;
}

/**
 * One question, one timer. The countdown is computed from `presented_at`
 * (set server-side the first time this question was fetched) rather than
 * reset to `time_limit_seconds` on every mount — that is what makes a page
 * reload after a disconnect show the same remaining time instead of a fresh
 * clock, satisfying "resumable on disconnect" honestly rather than just
 * re-rendering the same component.
 */
export function TimedQuestion({
  question,
  questionNumber,
  totalQuestions,
  isSubmitting,
  onSubmit,
}: TimedQuestionProps) {
  const [transcript, setTranscript] = useState("");
  const submittedRef = useRef(false);

  const presentedAtMs = question.presented_at ? new Date(question.presented_at).getTime() : Date.now();
  const deadlineMs = presentedAtMs + question.time_limit_seconds * 1000;

  const [remainingSeconds, setRemainingSeconds] = useState(() =>
    Math.max(0, Math.round((deadlineMs - Date.now()) / 1000)),
  );

  // Reset local answer state when the question itself changes (advancing to
  // the next one), not on every render.
  useEffect(() => {
    setTranscript("");
    submittedRef.current = false;
  }, [question.id]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      const remaining = Math.max(0, Math.round((deadlineMs - Date.now()) / 1000));
      setRemainingSeconds(remaining);
      if (remaining === 0 && !submittedRef.current) {
        submittedRef.current = true;
        onSubmit(transcript, question.time_limit_seconds);
      }
    }, 1000);
    return () => window.clearInterval(interval);
    // `transcript` is read inside the interval via closure capture is stale
    // across renders, so it is included so the *latest* draft is what an
    // auto-submit-on-timeout sends.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deadlineMs, transcript]);

  function handleManualSubmit() {
    if (submittedRef.current) return;
    submittedRef.current = true;
    const timeTaken = Math.max(0, question.time_limit_seconds - remainingSeconds);
    onSubmit(transcript, timeTaken);
  }

  const isLow = remainingSeconds <= 30;
  const minutes = Math.floor(remainingSeconds / 60);
  const seconds = remainingSeconds % 60;

  return (
    <div className="space-y-4 rounded-2xl border border-rule bg-white p-6">
      <div className="flex items-center justify-between gap-4">
        <span className="font-mono text-xs text-slate-500">
          Question {questionNumber} of {totalQuestions}
        </span>
        <span
          className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-semibold tabular-nums ${
            isLow ? "bg-red-100 text-red-700" : "bg-slate-100 text-slate-700"
          }`}
          role="timer"
          aria-live="polite"
        >
          <Clock size={14} aria-hidden="true" />
          {minutes}:{seconds.toString().padStart(2, "0")}
        </span>
      </div>

      <p className="text-lg font-medium leading-relaxed text-ink">{question.prompt}</p>

      <textarea
        rows={8}
        autoFocus
        value={transcript}
        onChange={(event) => setTranscript(event.target.value)}
        disabled={isSubmitting || remainingSeconds === 0}
        placeholder="Answer in your own words — you won't be able to look at the repository while answering."
        className="w-full rounded border border-slate-300 bg-white px-4 py-3 text-sm text-slate-900 placeholder-slate-400 outline-none transition focus:border-ink focus:ring-2 focus:ring-verified/25 disabled:opacity-60"
      />

      <div className="flex items-center justify-between gap-3">
        <p className="text-xs text-slate-500">
          Submitting when time runs out saves whatever you've written so far.
        </p>
        <Button type="button" onClick={handleManualSubmit} isLoading={isSubmitting} disabled={isSubmitting}>
          Submit answer
        </Button>
      </div>
    </div>
  );
}
