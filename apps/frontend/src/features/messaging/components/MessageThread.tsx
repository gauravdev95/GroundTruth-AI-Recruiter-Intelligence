import { Send } from "lucide-react";
import { useState } from "react";

import { Button, EmptyState, ErrorState, Skeleton, useToast } from "@/components";
import { useAuthContext } from "@/features/auth";
import { parseApiError } from "@/lib/apiError";
import { cn } from "@/lib/utils";

import { useConversation, useSendMessage } from "../hooks/useMessaging";

/** Both sides of the marketplace loop render the exact same conversation —
 * only the base URL differs (`rolePrefix`), never the shape or the UI. */
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

  const submit = () => {
    const body = draft.trim();
    if (!body) return;
    sendMessage.mutate(body, {
      onSuccess: () => setDraft(""),
      onError: (error) => showToast(parseApiError(error)?.message ?? "Could not send message.", "error"),
    });
  };

  if (conversation.isPending) {
    return <Skeleton className="h-48 w-full" />;
  }

  if (conversation.isError) {
    return <ErrorState title="Could not load messages" description="Something went wrong." />;
  }

  const messages = conversation.data?.messages ?? [];

  return (
    <div className="flex flex-col rounded-2xl border border-rule bg-white">
      <div className="max-h-96 min-h-[10rem] flex-1 space-y-3 overflow-y-auto p-4">
        {messages.length === 0 ? (
          <EmptyState title="No messages yet" description="Start the conversation below." />
        ) : (
          messages.map((message) => {
            const isMine = message.sender_user_id === user?.id;
            return (
              <div key={message.id} className={cn("flex", isMine ? "justify-end" : "justify-start")}>
                <div
                  className={cn(
                    "max-w-[80%] rounded-2xl px-3.5 py-2 text-sm",
                    isMine ? "bg-ink text-white" : "border border-rule bg-panel text-ink",
                  )}
                >
                  <p className="whitespace-pre-wrap">{message.body}</p>
                  <p className={cn("mt-1 text-[10px]", isMine ? "text-white/60" : "text-slate-400")}>
                    {new Date(message.created_at).toLocaleString()}
                  </p>
                </div>
              </div>
            );
          })
        )}
      </div>

      <form
        className="flex items-end gap-2 border-t border-rule p-3"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <textarea
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
          maxLength={4000}
          className="flex-1 resize-none rounded-xl border border-rule bg-panel px-3 py-2 text-sm text-ink placeholder:text-slate-400 focus:border-ink focus:outline-none"
        />
        <Button type="submit" size="sm" isLoading={sendMessage.isPending} disabled={!draft.trim()}>
          <Send size={14} aria-hidden="true" />
          Send
        </Button>
      </form>
    </div>
  );
}
