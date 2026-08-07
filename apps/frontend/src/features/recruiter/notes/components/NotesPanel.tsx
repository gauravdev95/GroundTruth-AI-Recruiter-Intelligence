import { EyeOff } from "lucide-react";
import { useState } from "react";

import { Button, useToast } from "@/components";
import { parseApiError } from "@/lib/apiError";

import { useAddNote, useNotes } from "../hooks/useNotes";

/** Team notes, visible to every recruiter at the same company
 * (`domains/pipeline/notes.py` scopes reads/writes to `company_id` at the
 * query layer) — but never to the candidate. The "Private" marker is not
 * decorative: it's the one thing this panel must never let a reader
 * mistake for something the candidate sees. */
export function NotesPanel({ applicationId }: { applicationId: string }) {
  const notes = useNotes(applicationId);
  const addNote = useAddNote(applicationId);
  const { showToast } = useToast();
  const [draft, setDraft] = useState("");

  const submit = () => {
    const body = draft.trim();
    if (!body) return;
    addNote.mutate(body, {
      onSuccess: () => setDraft(""),
      onError: (error) => showToast(parseApiError(error)?.message ?? "Could not add note.", "error"),
    });
  };

  return (
    <div className="rounded-2xl border border-[var(--flagged)]/30 bg-[var(--flagged)]/10 p-4">
      <div className="mb-3 flex items-center gap-1.5 text-[var(--flagged)]">
        <EyeOff size={14} aria-hidden="true" />
        <p className="text-xs font-semibold uppercase tracking-wide">Private team notes — not visible to the candidate</p>
      </div>

      <div className="mb-3 space-y-2">
        {notes.isPending ? (
          <p className="text-xs text-[var(--muted)]">Loading…</p>
        ) : notes.data && notes.data.length > 0 ? (
          notes.data.map((note) => (
            <div key={note.id} className="rounded-xl border border-[var(--flagged)]/30 bg-[var(--panel)] p-3">
              <p className="whitespace-pre-wrap text-sm text-[var(--ink)]">{note.body}</p>
              <p className="mt-1 text-[11px] text-[var(--muted)]">{new Date(note.created_at).toLocaleString()}</p>
            </div>
          ))
        ) : (
          <p className="text-xs text-[var(--muted)]">No notes yet.</p>
        )}
      </div>

      <div className="flex items-end gap-2">
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          rows={2}
          maxLength={4000}
          placeholder="Add a private note for your team…"
          className="flex-1 resize-none rounded-xl border border-[var(--flagged)]/30 bg-[var(--panel)] px-3 py-2 text-sm text-[var(--ink)] placeholder:text-[var(--muted)] focus:border-[var(--flagged)]/60 focus:outline-none"
        />
        <Button type="button" size="sm" variant="secondary" onClick={submit} isLoading={addNote.isPending} disabled={!draft.trim()}>
          Add note
        </Button>
      </div>
    </div>
  );
}
