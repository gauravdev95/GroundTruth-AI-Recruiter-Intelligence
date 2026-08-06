import { useDraggable } from "@dnd-kit/core";
import { BadgeCheck, GripVertical } from "lucide-react";

import { cn } from "@/lib/utils";

import { MatchScore } from "../../components/MatchScore";
import { initialsFrom } from "../lib/cardIdentity";
import type { ApplicationStatus } from "../api/pipelineApi";

export interface CandidateCardData {
  /** Stable identity for dnd-kit and for React. Application id where one
   * exists, candidate id in the `matched` column where one does not. */
  dragId: string;
  candidateProfileId: string;
  applicationId: string | null;
  status: ApplicationStatus | null;
  headline: string | null;
  score: number | null;
  matchedSkills: string[];
  reasoning: string;
  isVerified: boolean;
}

export interface CandidateCardProps {
  card: CandidateCardData;
  onOpen: (card: CandidateCardData) => void;
  /** Cards in `matched` have no application and therefore no legal move —
   * see `lib/columns.ts::ALLOWED_MOVES`. */
  draggable: boolean;
  selected: boolean;
  onToggleSelected: (dragId: string) => void;
  /** Set for a card that arrived over the socket since this board mounted.
   * Drives the entrance animation and nothing else. */
  isNew?: boolean;
  /** Rendered inside the drag overlay, where interaction is meaningless. */
  isOverlay?: boolean;
}

export function CandidateCard({
  card,
  onOpen,
  draggable,
  selected,
  onToggleSelected,
  isNew,
  isOverlay,
}: CandidateCardProps) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: card.dragId,
    disabled: !draggable || isOverlay,
    data: { card },
  });

  return (
    <div
      ref={isOverlay ? undefined : setNodeRef}
      className={cn(
        "group relative rounded-xl border bg-white p-2.5 transition",
        selected ? "border-gt-electric ring-1 ring-gt-electric/30" : "border-rule hover:border-ink/30",
        // The original stays in place at low opacity rather than being
        // removed: a column that reflows the instant you pick a card up moves
        // the drop target out from under the cursor.
        isDragging && !isOverlay ? "opacity-40" : null,
        isOverlay ? "cursor-grabbing shadow-raised" : null,
        isNew ? "animate-slide-up" : null,
      )}
    >
      <div className="flex items-start gap-2">
        {draggable && !isOverlay ? (
          <button
            type="button"
            {...attributes}
            {...listeners}
            aria-label={`Move ${card.headline ?? "candidate"}`}
            className="-ml-1 mt-0.5 shrink-0 cursor-grab touch-none rounded p-0.5 text-slate-300 opacity-0 transition hover:text-slate-500 focus-visible:opacity-100 group-hover:opacity-100"
          >
            <GripVertical size={13} aria-hidden="true" />
          </button>
        ) : null}

        <div className="min-w-0 flex-1">
          {/* Row 1 — avatar, verification, score. */}
          <div className="flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-ink/5 text-[10px] font-semibold text-slate-600"
            >
              {initialsFrom(card.headline)}
            </span>
            {card.isVerified ? (
              <BadgeCheck
                size={13}
                className="shrink-0 text-verified"
                aria-label="Verified — evidence and a completed interview"
              />
            ) : null}
            <span className="ml-auto shrink-0">
              <MatchScore score={card.score} withLabel={false} />
            </span>
          </div>

          {/* Row 2 — identity. The headline is what the recruiter has; see
              `initialsFrom` on why there is no name here. */}
          <button
            type="button"
            onClick={() => onOpen(card)}
            className="mt-1.5 block w-full truncate text-left text-[13px] font-medium text-ink hover:underline"
            title={card.headline ?? undefined}
          >
            {card.headline ?? "Candidate"}
          </button>

          {/* Row 3 — top matched skills. */}
          {card.matchedSkills.length > 0 ? (
            <p className="mt-1 truncate text-[11px] text-slate-500" title={card.matchedSkills.join(" · ")}>
              {card.matchedSkills.join(" · ")}
            </p>
          ) : null}

          {/* Row 4 — the reasoning string, verbatim from the server. */}
          {card.reasoning ? (
            <p className="mt-1 line-clamp-2 text-[11px] leading-snug text-slate-400">{card.reasoning}</p>
          ) : null}
        </div>
      </div>

      {!isOverlay ? (
        <input
          type="checkbox"
          checked={selected}
          onChange={() => onToggleSelected(card.dragId)}
          aria-label={`Select ${card.headline ?? "candidate"}`}
          className={cn(
            "absolute right-2 top-2 h-3.5 w-3.5 rounded border-slate-300 accent-gt-electric transition",
            // Hidden until it is useful, so a scanning recruiter sees data
            // rather than a column of empty checkboxes — but always present
            // once anything is selected, because a selection you cannot see
            // the extent of is worse than a little visual noise.
            selected ? "opacity-100" : "opacity-0 focus-visible:opacity-100 group-hover:opacity-100",
          )}
        />
      ) : null}
    </div>
  );
}
