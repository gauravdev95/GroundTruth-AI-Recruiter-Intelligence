import { ArrowRightLeft, Bell, MessageSquare, RefreshCcw } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Skeleton } from "@/components";
import { cn } from "@/lib/utils";

import type { Notification, NotificationType } from "../api/notificationsApi";
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

/**
 * The two notification types the backend returns, and nothing else — the
 * categories in this dropdown are the API's own `NotificationType` union, not
 * a taxonomy invented for the redesign. Each gets its own icon and label so a
 * message and a pipeline move stop reading as the same event.
 */
const CATEGORY: Record<NotificationType, { label: string; Icon: typeof MessageSquare }> = {
  new_message: { label: "Message", Icon: MessageSquare },
  stage_change: { label: "Application update", Icon: ArrowRightLeft },
};

/**
 * The header bell, shared by both dashboards (mounted via `headerExtra` in
 * each `DashboardLayout`; the destination route differs by role, so the
 * caller supplies `applicationHref`).
 *
 * Unread is marked with the app accent (`--violet`), never a status colour:
 * an unread notification is not a verified claim (`--verified`, green) and
 * not a failure (`--failed`, red) — the old green dot and red count badge
 * spent both meanings on something neither means. The count badge is violet
 * for the same reason.
 *
 * The panel is opaque `--panel-raised`, like every floating surface: the old
 * translucent `--panel` let scrolled dashboard content show through the list.
 * Width is capped against the viewport (`min(21rem, 100vw - 2rem)`) so the
 * panel cannot overflow a phone screen.
 */
export function NotificationBell({ applicationHref }: { applicationHref: (applicationId: string) => string }) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
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
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
      }
    };
    document.addEventListener("mousedown", onClickOutside);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onClickOutside);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open ]);

  const unreadCount = notifications.data?.unread_count ?? 0;
  const items = notifications.data?.notifications ?? [];

  return (
    <div className="relative" ref={containerRef}>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={unreadCount > 0 ? `${unreadCount} unread notifications` : "Notifications"}
        aria-expanded={open}
        aria-haspopup="true"
        className="relative rounded-[var(--r-sm)] p-2 text-[var(--muted)] transition hover:bg-[var(--panel-raised)] hover:text-[var(--ink)]"
      >
        <Bell size={18} />
        {unreadCount > 0 ? (
          <span className="tabular absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-[var(--violet)] px-1 text-[10px] font-semibold leading-none text-white">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        ) : null}
      </button>

      {open ? (
        <div className="absolute right-0 z-30 mt-2 w-[min(21rem,calc(100vw-2rem))] overflow-hidden rounded-[var(--r-lg)] border border-[var(--rule)] bg-[var(--panel-raised)] shadow-[var(--shadow-raised)]">
          <div className="flex items-center justify-between border-b border-[var(--rule-soft)] px-4 py-3">
            <p className="text-sm font-semibold text-[var(--ink)]">
              Notifications
              {unreadCount > 0 ? (
                <span className="tabular ml-2 text-xs font-medium text-[var(--muted)]">
                  {unreadCount} unread
                </span>
              ) : null}
            </p>
            <button
              type="button"
              onClick={() => notifications.refetch()}
              aria-label="Refresh notifications"
              title="Refresh notifications"
              className="rounded-[var(--r-sm)] p-1.5 text-[var(--muted)] transition hover:bg-[var(--panel)] hover:text-[var(--ink)]"
            >
              <RefreshCcw size={14} />
            </button>
          </div>

          <div className="max-h-[min(24rem,calc(100vh-8rem))] overflow-y-auto p-2">
            {notifications.isPending ? (
              <ul className="space-y-2 p-1" aria-label="Loading notifications">
                {[0, 1, 2].map((i) => (
                  <li key={i} className="flex items-start gap-3 px-2 py-2">
                    <Skeleton className="mt-0.5 size-8 shrink-0 rounded-full" />
                    <div className="flex-1 space-y-2">
                      <Skeleton className="h-3.5 w-4/5" />
                      <Skeleton className="h-3 w-1/3" />
                    </div>
                  </li>
                ))}
              </ul>
            ) : notifications.isError ? (
              <div className="flex flex-col items-center gap-2 px-4 py-8 text-center">
                <p className="text-sm font-medium text-[var(--ink)]">Couldn&apos;t load notifications</p>
                <p className="text-xs text-[var(--muted)]">Check your connection and try again.</p>
                <button
                  type="button"
                  onClick={() => notifications.refetch()}
                  className="mt-1 rounded-[var(--r-sm)] border border-[var(--rule)] px-3 py-1.5 text-xs font-medium text-[var(--ink)] transition hover:bg-[var(--panel)]"
                >
                  Try again
                </button>
              </div>
            ) : items.length > 0 ? (
              <ul className="space-y-0.5">
                {items.map((n) => {
                  const applicationId = n.payload.application_id as string | undefined;
                  const unread = n.read_at === null;
                  const { label, Icon } = CATEGORY[n.type];
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
                          "flex w-full items-start gap-3 rounded-[var(--r-md)] px-2.5 py-2.5 text-left text-sm transition hover:bg-[var(--panel)]",
                          unread && "bg-[var(--violet)]/[0.06]",
                        )}
                      >
                        <span
                          aria-hidden="true"
                          className={cn(
                            "mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full",
                            unread
                              ? "bg-[var(--violet)]/15 text-[var(--violet)]"
                              : "bg-[var(--panel)] text-[var(--muted)]",
                          )}
                        >
                          <Icon size={15} />
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--muted)]">
                            {label}
                          </span>
                          <span
                            className={cn(
                              "mt-0.5 block leading-snug",
                              unread ? "font-medium text-[var(--ink)]" : "text-[var(--slate)]",
                            )}
                          >
                            {notificationText(n)}
                          </span>
                          <span className="tabular mt-0.5 block text-xs text-[var(--muted)]">
                            {timeAgo(n.created_at)}
                          </span>
                        </span>
                        {unread ? (
                          <span
                            className="mt-2 size-2 shrink-0 rounded-full bg-[var(--violet)]"
                            aria-label="Unread"
                          />
                        ) : null}
                      </button>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <div className="flex flex-col items-center gap-2 px-4 py-8 text-center">
                <span
                  aria-hidden="true"
                  className="flex size-10 items-center justify-center rounded-full bg-[var(--panel)] text-[var(--muted)]"
                >
                  <Bell size={18} />
                </span>
                <p className="text-sm font-medium text-[var(--ink)]">You&apos;re all caught up.</p>
                <p className="text-xs leading-relaxed text-[var(--muted)]">
                  New messages and application updates will appear here.
                </p>
              </div>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
