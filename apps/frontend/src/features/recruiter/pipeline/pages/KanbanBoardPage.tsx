import {
  DndContext,
  DragOverlay,
  PointerSensor,
  KeyboardSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { ArrowLeft, Download, MessageSquare, Pencil } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Button, ErrorState, Skeleton, useToast } from "@/components";
import { parseApiError } from "@/lib/apiError";

import { EvidenceDrawer, type EvidenceDrawerCandidate } from "../../evidence/components/EvidenceDrawer";
import { useJob } from "../../hooks/useJobs";
import type { ApplicationStatus, PipelineBoard } from "../api/pipelineApi";
import { CandidateCard, type CandidateCardData } from "../components/CandidateCard";
import { DropZone, KanbanColumn } from "../components/KanbanColumn";
import { RejectionReasonModal } from "../components/RejectionReasonModal";
import { useBoardTransition, usePipelineBoard } from "../hooks/usePipeline";
import { usePipelineRealtime } from "../hooks/usePipelineRealtime";
import { canMove, summarise, type DropZoneId } from "../lib/columns";
import { downloadBoardCsv } from "../lib/exportCsv";

/** The forward step each stage offers in the drawer, mirroring
 * `ALLOWED_MOVES`' non-rejection half. */
const NEXT_STAGE: Partial<Record<ApplicationStatus, { to: ApplicationStatus; label: string }>> = {
  applied: { to: "shortlisted", label: "Move to shortlist" },
  shortlisted: { to: "interview_scheduled", label: "Move to interviewing" },
  interview_scheduled: { to: "hired", label: "Mark as hired" },
};

function toCards(board: PipelineBoard) {
  const matched: CandidateCardData[] = board.matched.map((candidate) => ({
    dragId: `candidate:${candidate.candidate_profile_id}`,
    candidateProfileId: candidate.candidate_profile_id,
    applicationId: null,
    status: null,
    headline: candidate.headline,
    score: candidate.match_score,
    matchedSkills: candidate.matched_skills,
    reasoning: candidate.reasoning,
    isVerified: candidate.is_verified,
  }));

  const fromApplications = (key: keyof PipelineBoard): CandidateCardData[] =>
    (board[key] as PipelineBoard["applied"]).map((application) => ({
      dragId: `application:${application.application_id}`,
      candidateProfileId: application.candidate_profile_id,
      applicationId: application.application_id,
      status: application.status as ApplicationStatus,
      headline: application.headline,
      // The *live* score, which is what a review decision should be made
      // against. `score_at_apply` still drives column ordering server-side.
      score: application.match_score,
      matchedSkills: application.matched_skills,
      reasoning: application.reasoning,
      isVerified: application.is_verified,
    }));

  return {
    matched,
    applied: fromApplications("applied"),
    shortlisted: fromApplications("shortlisted"),
    interviewing: fromApplications("interview_scheduled"),
    hired: fromApplications("hired"),
    rejected: fromApplications("rejected"),
  };
}

/**
 * Screen 3 — `/recruiter/jobs/:jobId/pipeline`.
 *
 * Five columns over six server states (`lib/columns.ts`), drag-and-drop
 * limited to the transitions the server will actually accept, and a drawer
 * rather than a route for candidate review.
 *
 * **Nothing on this board rejects anybody on its own.** Every move here is a
 * drag or a click a recruiter performed; there is no threshold, no expiry and
 * no batch process that closes a candidate. That is enforced at the other end
 * too — `transition_status` has no system caller — but it is worth stating
 * where the affordances live.
 */
export function KanbanBoardPage() {
  const { jobId = "" } = useParams<{ jobId: string }>();
  const { showToast } = useToast();

  const job = useJob(jobId);
  const board = usePipelineBoard(jobId);
  const transition = useBoardTransition(jobId);

  const [openCard, setOpenCard] = useState<CandidateCardData | null>(null);
  const [draggingCard, setDraggingCard] = useState<CandidateCardData | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  /** Set when a move needs a reason before it commits. Holds the pending move
   * so Skip and Submit resolve to the same transition. */
  const [pendingClose, setPendingClose] = useState<CandidateCardData | null>(null);

  const cards = useMemo(() => (board.data ? toCards(board.data) : null), [board.data]);
  const matchedIds = useMemo(
    () => board.data?.matched.map((c) => c.candidate_profile_id) ?? [],
    [board.data],
  );
  const arrivals = usePipelineRealtime(jobId, matchedIds);

  const sensors = useSensors(
    // A small activation distance, so clicking a card to open the drawer is
    // not read as the start of a drag. Without it every click is a 0px drag
    // and the drawer never opens.
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor),
  );

  const move = (card: CandidateCardData, to: ApplicationStatus, feedback?: { closeReason?: never }) => {
    if (!card.applicationId) return;
    transition.mutate(
      { applicationId: card.applicationId, toStatus: to, ...feedback },
      {
        onError: (error) =>
          // Surfaced verbatim: the server's message names the rule that
          // refused (`ALLOWED_TRANSITIONS`), which is the sentence a
          // recruiter needs rather than "something went wrong".
          showToast(parseApiError(error)?.message ?? "Could not move this candidate.", "error"),
      },
    );
  };

  const onDragEnd = (event: DragEndEvent) => {
    setDraggingCard(null);
    const card = event.active.data.current?.card as CandidateCardData | undefined;
    const zone = event.over?.id as DropZoneId | undefined;
    if (!card || !zone || !card.status || !canMove(card.status, zone)) return;

    if (zone === "rejected") {
      // The reason modal is the *only* thing between the drop and the move;
      // Skip inside it commits immediately. See `RejectionReasonModal`.
      setPendingClose(card);
      return;
    }
    move(card, zone as ApplicationStatus);
  };

  const toggleSelected = (dragId: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(dragId)) next.delete(dragId);
      else next.add(dragId);
      return next;
    });

  const selectedApplicationIds = useMemo(
    () =>
      [...selected]
        .filter((id) => id.startsWith("application:"))
        .map((id) => id.slice("application:".length)),
    [selected],
  );

  const backLink = (
    <Link
      to={`/recruiter/jobs/${jobId}`}
      className="inline-flex items-center gap-1.5 text-sm text-[var(--slate)] transition hover:text-[var(--ink)]"
    >
      <ArrowLeft size={14} aria-hidden="true" /> Job
    </Link>
  );

  if (board.isPending) {
    return (
      <div className="space-y-4">
        {backLink}
        <Skeleton className="h-[28rem] w-full" />
      </div>
    );
  }

  if (board.isError || !board.data || !cards) {
    return (
      <div className="space-y-4">
        {backLink}
        <ErrorState
          title="Could not load the pipeline"
          description="Something went wrong."
          action={
            <Button type="button" variant="secondary" size="sm" onClick={() => void board.refetch()}>
              Try again
            </Button>
          }
        />
      </div>
    );
  }

  const data = board.data;
  const renderCard = (card: CandidateCardData, draggable: boolean) => (
    <CandidateCard
      key={card.dragId}
      card={card}
      draggable={draggable}
      selected={selected.has(card.dragId)}
      onToggleSelected={toggleSelected}
      onOpen={setOpenCard}
      isNew={arrivals.has(card.candidateProfileId)}
    />
  );

  const drawerCandidate: EvidenceDrawerCandidate | null = openCard
    ? {
        candidateProfileId: openCard.candidateProfileId,
        applicationId: openCard.applicationId,
        headline: openCard.headline,
        score: openCard.score,
        reasoning: openCard.reasoning,
        appliedAt:
          data.applied.concat(data.shortlisted, data.interview_scheduled, data.hired, data.rejected)
            .find((a) => a.application_id === openCard.applicationId)?.applied_at ?? null,
        nextStage:
          openCard.status && NEXT_STAGE[openCard.status]
            ? {
                label: NEXT_STAGE[openCard.status]!.label,
                onMove: () => {
                  move(openCard, NEXT_STAGE[openCard.status!]!.to);
                  setOpenCard(null);
                },
              }
            : null,
        onDismiss:
          openCard.status && canMove(openCard.status, "rejected")
            ? () => {
                setPendingClose(openCard);
                setOpenCard(null);
              }
            : null,
      }
    : null;

  return (
    <div className="space-y-4">
      {backLink}

      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <h1 className="font-display text-2xl font-semibold tracking-tight text-[var(--ink)]">
              {job.data?.job.title ?? "Pipeline"}
            </h1>
            <Link
              to={`/recruiter/jobs/${jobId}`}
              className="inline-flex items-center gap-1 text-xs text-[var(--slate)] transition hover:text-[var(--ink)]"
            >
              <Pencil size={11} aria-hidden="true" /> Edit job
            </Link>
          </div>
          <p className="tabular mt-0.5 text-sm text-[var(--slate)]">{summarise(data)}</p>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            disabled={selectedApplicationIds.length === 0}
            title={
              selectedApplicationIds.length === 0
                ? "Select applied candidates to message them"
                : undefined
            }
            onClick={() =>
              // One conversation per application (`conversations.application_id`
              // is unique), so bulk messaging is N sends, not a broadcast
              // primitive the API does not have. Routed through the existing
              // per-application thread rather than opening a composer that
              // would need its own endpoint.
              showToast(
                `Open each of the ${selectedApplicationIds.length} selected candidates to message them — conversations are per application.`,
                "info",
              )
            }
          >
            <MessageSquare size={13} aria-hidden="true" />
            Message{selectedApplicationIds.length > 0 ? ` (${selectedApplicationIds.length})` : ""}
          </Button>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => downloadBoardCsv(data, job.data?.job.title ?? "job")}
          >
            <Download size={13} aria-hidden="true" />
            Export
          </Button>
        </div>
      </header>

      <DndContext
        sensors={sensors}
        onDragStart={(event: DragStartEvent) =>
          setDraggingCard((event.active.data.current?.card as CandidateCardData) ?? null)
        }
        onDragCancel={() => setDraggingCard(null)}
        onDragEnd={onDragEnd}
      >
        {/* Horizontal scroll below ~1400px. Columns keep their width rather
            than compressing: five 200px columns are five unreadable columns. */}
        <div className="flex gap-3 overflow-x-auto pb-3">
          <KanbanColumn
            header="MATCHED"
            count={cards.matched.length}
            emptyHint="Candidates appear here as the matching engine finds them. Nothing to do — they arrive on their own."
          >
            {/* Not a drop target and not draggable: a matched candidate has no
                application, and only the student can create one. */}
            {cards.matched.map((card) => renderCard(card, false))}
          </KanbanColumn>

          <KanbanColumn
            header="APPLIED"
            count={cards.applied.length}
            emptyHint="Nobody has applied yet."
          >
            <DropZone id="applied" isAllowed={false} isDraggingAny={Boolean(draggingCard)}>
              {cards.applied.map((card) => renderCard(card, true))}
            </DropZone>
          </KanbanColumn>

          <KanbanColumn
            header="SHORTLISTED"
            count={cards.shortlisted.length}
            emptyHint="Drag candidates here from Applied."
          >
            <DropZone
              id="shortlisted"
              isAllowed={Boolean(draggingCard?.status && canMove(draggingCard.status, "shortlisted"))}
              isDraggingAny={Boolean(draggingCard)}
              className="min-h-[3rem]"
            >
              {cards.shortlisted.map((card) => renderCard(card, true))}
            </DropZone>
          </KanbanColumn>

          <KanbanColumn
            header="INTERVIEWING"
            count={cards.interviewing.length}
            emptyHint="Move a shortlisted candidate here once an interview is booked."
          >
            <DropZone
              id="interview_scheduled"
              isAllowed={Boolean(
                draggingCard?.status && canMove(draggingCard.status, "interview_scheduled"),
              )}
              isDraggingAny={Boolean(draggingCard)}
              className="min-h-[3rem]"
            >
              {cards.interviewing.map((card) => renderCard(card, true))}
            </DropZone>
          </KanbanColumn>

          {/* Two outcomes, one column, split by their own drop targets —
              dropping into Offer and dropping into Closed are opposite
              decisions and cannot share a target. */}
          <KanbanColumn
            header="OFFER · CLOSED"
            count={cards.hired.length + cards.rejected.length}
            emptyHint="Final states. Nothing lands here without you putting it here."
          >
            <DropZone
              id="hired"
              isAllowed={Boolean(draggingCard?.status && canMove(draggingCard.status, "hired"))}
              isDraggingAny={Boolean(draggingCard)}
              className="min-h-[2.5rem] space-y-2 p-1"
            >
              <p className="px-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--verified)]">
                Offer
              </p>
              {cards.hired.map((card) => (
                <div key={card.dragId} className="border-l-2 border-[var(--verified)] pl-1.5">
                  {renderCard(card, false)}
                </div>
              ))}
            </DropZone>

            <DropZone
              id="rejected"
              isAllowed={Boolean(draggingCard?.status && canMove(draggingCard.status, "rejected"))}
              isDraggingAny={Boolean(draggingCard)}
              className="mt-2 min-h-[2.5rem] space-y-2 p-1"
            >
              <p className="px-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--failed)]">
                Closed
              </p>
              {cards.rejected.map((card) => (
                <div key={card.dragId} className="border-l-2 border-[var(--failed)] pl-1.5">
                  {renderCard(card, false)}
                </div>
              ))}
            </DropZone>
          </KanbanColumn>
        </div>

        {/* The overlay is what follows the cursor. Rendering the original in
            place at reduced opacity keeps the source column from collapsing
            under the pointer mid-drag. */}
        <DragOverlay dropAnimation={null}>
          {draggingCard ? (
            <div className="w-[248px]">
              <CandidateCard
                card={draggingCard}
                draggable={false}
                selected={false}
                onToggleSelected={() => {}}
                onOpen={() => {}}
                isOverlay
              />
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>

      <EvidenceDrawer
        candidate={drawerCandidate}
        jobId={jobId}
        onClose={() => setOpenCard(null)}
        isMoving={transition.isPending}
      />

      <RejectionReasonModal
        open={pendingClose !== null}
        candidateLabel={pendingClose?.headline ?? "this candidate"}
        isSaving={transition.isPending}
        onCancel={() => setPendingClose(null)}
        onSubmit={(feedback) => {
          const card = pendingClose;
          setPendingClose(null);
          if (!card?.applicationId) return;
          transition.mutate(
            { applicationId: card.applicationId, toStatus: "rejected", ...feedback },
            {
              onError: (error) =>
                showToast(parseApiError(error)?.message ?? "Could not close this candidate.", "error"),
            },
          );
        }}
      />
    </div>
  );
}
