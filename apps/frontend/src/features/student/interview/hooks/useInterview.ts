import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

import { queryKeys } from "@/lib/queryKeys";

import { interviewApi, type InterviewState, type InterviewTurn } from "../api/interviewApi";
import { InterviewSocket, type InterviewSocketEvent } from "../lib/interviewSocket";

/** 404 ("no attempt yet") is the common, expected first response for a
 * freshly-verified repository — never retried, and callers branch on
 * `isError` to render the "start interview" screen rather than an error. */
export function useLatestInterview(projectId: string) {
  return useQuery({
    queryKey: queryKeys.interview.latestForProject(projectId),
    queryFn: () => interviewApi.latestForProject(projectId),
    retry: false,
  });
}

export function useStartInterview() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: interviewApi.start,
    onSuccess: (interview) => {
      if (interview.project_id) {
        queryClient.setQueryData(queryKeys.interview.latestForProject(interview.project_id), interview);
      }
    },
  });
}

/** Polls only while a worker is doing something the candidate is waiting on:
 * question generation before the session opens (`pending`) and scoring after
 * it closes (`evaluating`). During the conversation itself the socket pushes
 * state, so polling would be duplicate work on the one screen that cannot
 * afford noise. */
const POLLING_STATUSES = new Set(["pending", "evaluating"]);

export function useInterviewState(interviewId: string | null) {
  return useQuery({
    queryKey: queryKeys.interview.state(interviewId ?? ""),
    queryFn: () => interviewApi.getState(interviewId as string),
    enabled: interviewId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.interview.status;
      return status && POLLING_STATUSES.has(status) ? 2500 : false;
    },
    refetchIntervalInBackground: true,
  });
}

export function useEvidenceReport(interviewId: string, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.interview.report(interviewId),
    queryFn: () => interviewApi.getReport(interviewId),
    enabled,
  });
}

export type ConnectionState = "connecting" | "live" | "reconnecting" | "unavailable";

/** A turn the candidate has sent that the server has not confirmed yet.
 * Rendered so the conversation reads normally, and marked so a message lost to
 * a dropped socket is visibly lost rather than silently gone. */
export interface PendingTurn {
  text: string;
  failed: boolean;
}

export interface LiveInterview {
  state: InterviewState | null;
  transcript: InterviewTurn[];
  pending: PendingTurn | null;
  isThinking: boolean;
  connection: ConnectionState;
  error: string | null;
  timeRemaining: number;
  send: (text: string) => void;
}

/**
 * Drives one live interview: the socket, the optimistic echo of what the
 * candidate just said, and the countdown between server updates.
 *
 * The socket is the fast path, not the only path. If it never opens — a proxy
 * that strips WebSockets, a corporate network that blocks them — sending falls
 * back to `POST /turns`, which runs exactly the same server-side turn. The
 * candidate loses the "thinking" indicator and gains a slower feel; they do not
 * lose the interview.
 */
export function useLiveInterview(interviewId: string | null, enabled: boolean): LiveInterview {
  const queryClient = useQueryClient();
  const [state, setState] = useState<InterviewState | null>(null);
  const [pending, setPending] = useState<PendingTurn | null>(null);
  const [isThinking, setIsThinking] = useState(false);
  const [connection, setConnection] = useState<ConnectionState>("connecting");
  const [error, setError] = useState<string | null>(null);
  const [timeRemaining, setTimeRemaining] = useState(0);
  const socketRef = useRef<InterviewSocket | null>(null);

  const applyState = useCallback(
    (next: InterviewState) => {
      setState(next);
      setTimeRemaining(next.time_remaining_seconds);
      setIsThinking(false);
      setPending(null);
      // Keep the query cache honest: the page reads `useInterviewState` for
      // status transitions (evaluating -> completed), and a socket update that
      // left the cache stale would show a finished interview as still running.
      if (interviewId) {
        queryClient.setQueryData(queryKeys.interview.state(interviewId), next);
      }
    },
    [interviewId, queryClient],
  );

  useEffect(() => {
    if (!interviewId || !enabled) return;

    const socket = new InterviewSocket(interviewId, (event: InterviewSocketEvent) => {
      switch (event.type) {
        case "connected":
          setConnection("live");
          setError(null);
          applyState(event.state);
          return;
        case "state":
          setConnection("live");
          applyState(event.state);
          return;
        case "thinking":
          setIsThinking(true);
          return;
        case "error":
          setIsThinking(false);
          setPending((current) => (current ? { ...current, failed: true } : null));
          setError(event.message);
          return;
        case "closed":
          setIsThinking(false);
          setConnection(event.permanent ? "unavailable" : "reconnecting");
          return;
      }
    });

    socketRef.current = socket;
    socket.connect();

    return () => {
      socket.close();
      socketRef.current = null;
    };
  }, [interviewId, enabled, applyState]);

  // The countdown ticks client-side between server updates, and every server
  // update overwrites it. The server's number is the only one that decides
  // anything — this exists so the clock does not visibly freeze between turns.
  useEffect(() => {
    if (!enabled || timeRemaining <= 0) return;
    const timer = setInterval(() => setTimeRemaining((seconds) => Math.max(0, seconds - 1)), 1000);
    return () => clearInterval(timer);
  }, [enabled, timeRemaining]);

  const restFallback = useMutation({
    mutationFn: (text: string) => interviewApi.submitTurn(interviewId as string, text),
    onSuccess: applyState,
    onError: () => {
      setIsThinking(false);
      setPending((current) => (current ? { ...current, failed: true } : null));
      setError("That answer could not be sent. Try again.");
    },
  });

  const send = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || !interviewId) return;

      setError(null);
      setPending({ text: trimmed, failed: false });
      setIsThinking(true);

      if (!socketRef.current?.send(trimmed)) {
        restFallback.mutate(trimmed);
      }
    },
    [interviewId, restFallback],
  );

  return {
    state,
    transcript: state?.transcript ?? [],
    pending,
    isThinking,
    connection,
    error,
    timeRemaining,
    send,
  };
}
