import { MessageSquare, Send } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button, EmptyState, ErrorState, Skeleton, useToast } from "@/components";
import { useAuthContext } from "@/features/auth";
import { parseApiError } from "@/lib/apiError";
import { cn } from "@/lib/utils";

import { useConversation, useSendMessage } from "../hooks/useMessaging";

const MAX_LENGTH = 4000;

/** Same-day messages show the clock time only; older ones get the date too,
 * so a week-old reply does not pretend to be from today. */
function formatMessageTime(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  const sameDay = date.toDateString() === now.toDateString();
  const time = date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  if (sameDay) return time;
  return `${date.toLocaleDateString([], { month: "short", day: "numeric" })} · ${time}`;
}

/** Both sides of the marketplace loop render the exact same conversation —
 * only the base URL differs (`rolePrefix`), never the shape or the UI. The
 * other side's label is derived from that same prop: on the recruiter side
 * the other party is the candidate, on the student side it is the recruiter.
 * No name is shown because the API returns only `sender_user_id`, and a
 * name invented here would be a fabrication.
 *
 * The list is `role="log"`: a reply arriving on the 15s poll is announced to
 * assistive tech, and the view scrolls to the newest message on arrival.
 * The scroll is an instant jump, never smooth — smooth scrolling would fight
 * `prefers-reduced-motion` and the poll. */
export function MessageThread({
  rolePrefix,
  applicationId,
}: {
  rolePrefix: "student" | "recruiter";
  applicationId: string;
}) {
  const { user } = useAuthContext();
  const conversation = useConversation(rolePrefix, applicationId);
  const sendMessage = useSendMessage(rolePrefix, applicationId);
  const { showToast } = useToast();
  const [draft, setDraft] = useState("");
  const listRef = useRef<HTMLDivElement>(null);

  const messages = conversation.data?.messages ?? [];

  useEffect(() => {
    const list = listRef.current;
    if (list) list.scrollTop = list.scrollHeight;
  }, [messages.length]);

  const submit = () => {
    const body = draft.trim();
    if (!body) return;
    sendMessage.mutate(body, {
      onSuccess: () => setDraft(""),
      onError: (error) => showToast(parseApiError(error)?.message ?? "Could not send message.", "error"),
    });
  };

  if (conversation.isPending) {
    return (
      <div
        className="flex flex-col rounded-2xl border border-[var(--rule)] bg-[var(--panel)]"
        aria-label="Loading messages"
      >
        <div className="flex-1 space-y-3 p-4">
          <div className="flex justify-start">
            <Skeleton className="h-10 w-3/5 rounded-2xl" />
          </div>
          <div className="flex justify-end">
            <Skeleton className="h-10 w-1/2 rounded-2xl" />
          </div>
          <div className="flex justify-start">
            <Skeleton className="h-10 w-2/5 rounded-2xl" />
          </div>
        </div>
        <div className="border-t border-[var(--rule)] p-3">
          <Skeleton className="h-10 w-full rounded-xl" />
        </div>
      </div>
    );
  }

  if (conversation.isError) {
    return (
      <ErrorState
        title="Could not load messages"
        description="Something went wrong."
        action={
          <Button type="button" size="sm" variant="secondary" onClick={() => conversation.refetch()}>
            Try again
          </Button>
        }
      />
    );
  }

  const otherLabel = rolePrefix === "recruiter" ? "Candidate" : "Recruiter";

  return (
    <div className="flex flex-col rounded-2xl border border-[var(--rule)] bg-[var(--panel)]">
      <div
        ref={listRef}
        role="log"
        aria-live="polite"
        aria-label="Conversation"
        className="max-h-96 min-h-[10rem] flex-1 space-y-4 overflow-y-auto p-4"
      >
        {messages.length === 0 ? (
          <EmptyState
            icon={MessageSquare}
            title="No messages yet"
            description="Start the conversation below."
          />
        ) : (
          messages.map((message) => {
            const isMine = message.sender_user_id === user?.id;
            return (
              <div key={message.id} className={cn("flex flex-col", isMine ? "items-end" : "items-start")}>
                <span className="mb-1 text-[11px] font-medium text-[var(--muted)]">
                  {isMine ? "You" : otherLabel}
                </span>
                <div
                  className={cn(
                    "max-w-[80%] rounded-2xl px-3.5 py-2 text-sm leading-relaxed",
                    isMine
                      ? "rounded-br-md bg-[var(--violet)] text-white"
                      : "rounded-bl-md border border-[var(--rule)] bg-[var(--panel-raised)] text-[var(--ink)]",
                  )}
                >
                  <p className="whitespace-pre-wrap break-words">{message.body}</p>
                  <p
                    className={cn(
                      "tabular mt-1 text-right text-[10px]",
                      isMine ? "text-white/60" : "text-[var(--muted)]",
                    )}
                  >
                    {formatMessageTime(message.created_at)}
                  </p>
                </div>
              </div>
            );
          })
        )}
      </div>

      <form
        className="border-t border-[var(--rule)] p-3"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <div className="flex items-end gap-2">
          <label htmlFor={`message-${applicationId}`} className="sr-only">
            Write a message
          </label>
          <textarea
            id={`message-${applicationId}`}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            placeholder="Write a message…"
            rows={2}
            maxLength={MAX_LENGTH}
            disabled={sendMessage.isPending}
            className="flex-1 resize-none rounded-xl border border-[var(--rule)] bg-[var(--panel)] px-3 py-2 text-sm text-[var(--ink)] placeholder:text-[var(--muted)] transition focus:border-[var(--violet)] focus:outline-none focus:ring-2 focus:ring-[var(--violet)]/25 disabled:opacity-60"
          />
          <Button type="submit" size="sm" isLoading={sendMessage.isPending} disabled={!draft.trim()}>
            <Send size={14} aria-hidden="true" />
            Send
          </Button>
        </div>
        <div className="mt-2 flex items-center justify-between px-1 text-[11px] text-[var(--muted)]">
          <span>Enter to send · Shift + Enter for a new line</span>
          {draft.length > 0 ? (
            <span className="tabular" aria-label={`${draft.length} of ${MAX_LENGTH} characters used`}>
              {draft.length.toLocaleString()} / {MAX_LENGTH.toLocaleString()}
            </span>
          ) : null}
        </div>
      </form>
    </div>
  );
}
