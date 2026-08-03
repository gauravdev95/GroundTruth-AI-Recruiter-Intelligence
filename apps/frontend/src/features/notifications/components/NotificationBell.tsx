import { Bell, MessageSquare, RefreshCcw } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { cn } from "@/lib/utils";

import type { Notification } from "../api/notificationsApi";
import { useMarkNotificationRead, useNotifications } from "../hooks/useNotifications";

function timeAgo(iso: string): string {
  const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function notificationText(n: Notification): string {
  if (n.type === "new_message") {
    const jobTitle = n.payload.job_title as string | undefined;
    return jobTitle ? `New message about ${jobTitle}` : "New message";
  }
  const message = n.payload.message as string | undefined;
  if (message) return message;
  const jobTitle = n.payload.job_title as string | undefined;
  const status = n.payload.status as string | undefined;
  if (jobTitle && status) return `${jobTitle}: moved to ${status.replace(/_/g, " ")}`;
  return "Application update";
}

/** Notification `payload.application_id` is the only cross-role-safe
 * target — the destination route differs by which dashboard the bell is
 * mounted in, so the caller supplies a resolver rather than this component
 * hard-coding `/student/...` or `/recruiter/...`. */
export function NotificationBell({ applicationHref }: { applicationHref: (applicationId: string) => string }) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const notifications = useNotifications();
  const markRead = useMarkNotificationRead();
  const navigate = useNavigate();

  useEffect(() => {
    if (!open) return;
    const onClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [open]);

  const unreadCount = notifications.data?.unread_count ?? 0;

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={unreadCount > 0 ? `${unreadCount} unread notifications` : "Notifications"}
        className="relative rounded p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
      >
        <Bell size={18} />
        {unreadCount > 0 ? (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-semibold text-white">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        ) : null}
      </button>

      {open ? (
        <div className="absolute right-0 z-30 mt-2 w-80 rounded-2xl border border-slate-200 bg-white p-2 shadow-xl">
          <div className="flex items-center justify-between px-2 py-1.5">
            <p className="text-sm font-semibold text-ink">Notifications</p>
            <button
              type="button"
              onClick={() => notifications.refetch()}
              aria-label="Refresh notifications"
              className="text-slate-400 hover:text-ink"
            >
              <RefreshCcw size={14} />
            </button>
          </div>

          <div className="max-h-96 overflow-y-auto">
            {notifications.isPending ? (
              <p className="px-2 py-4 text-center text-xs text-slate-400">Loading…</p>
            ) : notifications.data && notifications.data.notifications.length > 0 ? (
              <ul className="space-y-1">
                {notifications.data.notifications.map((n) => {
                  const applicationId = n.payload.application_id as string | undefined;
                  const unread = n.read_at === null;
                  return (
                    <li key={n.id}>
                      <button
                        type="button"
                        onClick={() => {
                          if (unread) markRead.mutate(n.id);
                          setOpen(false);
                          if (applicationId) navigate(applicationHref(applicationId));
                        }}
                        className={cn(
                          "flex w-full items-start gap-2 rounded-xl px-2 py-2 text-left text-sm transition hover:bg-slate-50",
                          unread && "bg-ink/[0.03]",
                        )}
                      >
                        <MessageSquare size={14} className="mt-0.5 shrink-0 text-slate-400" aria-hidden="true" />
                        <span className="flex-1">
                          <span className={cn("block", unread ? "font-medium text-ink" : "text-slate-600")}>
                            {notificationText(n)}
                          </span>
                          <span className="text-xs text-slate-400">{timeAgo(n.created_at)}</span>
                        </span>
                        {unread ? <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-verified" aria-hidden="true" /> : null}
                      </button>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="px-2 py-4 text-center text-xs text-slate-400">You're all caught up.</p>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
