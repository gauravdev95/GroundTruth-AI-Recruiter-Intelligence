import { CheckCircle2 } from "lucide-react";
import { useState } from "react";

import { Badge, Button, Modal, useToast } from "@/components";
import { parseApiError } from "@/lib/apiError";

import { useSmartApply } from "../hooks/useApplications";

interface EvidenceItem {
  label: string;
}

/** "No data re-entry, show evidence being attached" — this is a preview,
 * not a form: everything listed here is already on the candidate's profile
 * and will be attached automatically (`pipeline/evidence.py::build_evidence_record`),
 * the only input is an optional note. */
export function SmartApplyModal({
  open,
  onClose,
  jobId,
  jobTitle,
  matchedSkills,
}: {
  open: boolean;
  onClose: () => void;
  jobId: string;
  jobTitle: string;
  matchedSkills: EvidenceItem[];
}) {
  const [coverNote, setCoverNote] = useState("");
  const smartApply = useSmartApply();
  const { showToast } = useToast();

  const submit = () => {
    smartApply.mutate(
      { jobId, coverNote: coverNote.trim() || null },
      {
        onSuccess: () => {
          showToast("Application sent.", "success");
          setCoverNote("");
          onClose();
        },
        onError: (error) => showToast(parseApiError(error)?.message ?? "Could not apply to this job.", "error"),
      },
    );
  };

  return (
    <Modal open={open} onClose={onClose} title={`Apply to ${jobTitle}`}>
      <div className="space-y-4">
        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-400">
            Evidence being attached — no re-entry needed
          </p>
          <ul className="space-y-1.5">
            <li className="flex items-center gap-2 text-sm text-ink">
              <CheckCircle2 size={14} className="text-verified" aria-hidden="true" />
              Your verified profile, skills, and match score
            </li>
            {matchedSkills.slice(0, 6).map((item) => (
              <li key={item.label} className="ml-6">
                <Badge variant="neutral">{item.label}</Badge>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <label htmlFor="cover-note" className="mb-1 block text-xs font-medium uppercase tracking-wide text-slate-400">
            Cover note (optional)
          </label>
          <textarea
            id="cover-note"
            value={coverNote}
            onChange={(e) => setCoverNote(e.target.value)}
            rows={4}
            maxLength={4000}
            placeholder="Anything you'd like to add for the recruiter…"
            className="w-full resize-none rounded-xl border border-rule bg-panel px-3 py-2 text-sm text-ink placeholder:text-slate-400 focus:border-ink focus:outline-none"
          />
        </div>

        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="button" onClick={submit} isLoading={smartApply.isPending}>
            Send application
          </Button>
        </div>
      </div>
    </Modal>
  );
}
