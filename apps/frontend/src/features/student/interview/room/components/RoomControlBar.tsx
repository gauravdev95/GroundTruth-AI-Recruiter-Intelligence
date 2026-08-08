import {
  FileText,
  Maximize2,
  Mic,
  MicOff,
  PhoneOff,
  Repeat,
  Video,
  VideoOff,
  Volume2,
  VolumeX,
} from "lucide-react";
import type { ReactNode } from "react";

/**
 * The control bar.
 *
 * Modelled on the one every candidate already knows: device toggles on the
 * left, secondary actions in the middle, the destructive action alone on the
 * right with clear separation. Nothing here is novel, on purpose — a candidate
 * about to be assessed should not have to learn an interface.
 *
 * Every control states what it does to a screen reader *and* what state it is
 * currently in, because the icons are the only other signal and a muted
 * microphone and a live one are one glyph apart.
 */

interface ControlButtonProps {
  onClick: () => void;
  label: string;
  icon: ReactNode;
  /** "off" renders the struck-through, danger-tinted state used by every call
   * product for a disabled device. */
  variant?: "default" | "off" | "danger";
  disabled?: boolean;
  pressed?: boolean;
}

function ControlButton({
  onClick,
  label,
  icon,
  variant = "default",
  disabled,
  pressed,
}: ControlButtonProps) {
  const styles =
    variant === "off"
      ? "bg-[var(--room-danger-dim)] text-[var(--room-danger)] hover:bg-[rgb(244_86_79/0.24)]"
      : variant === "danger"
        ? "bg-[var(--room-danger)] text-white hover:brightness-110"
        : "bg-[var(--room-raised)] text-[var(--room-ink)] hover:bg-[rgb(30_40_64/1)]";

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      aria-pressed={pressed}
      title={label}
      className={[
        "flex h-11 w-11 items-center justify-center rounded-full transition-colors",
        "disabled:cursor-not-allowed disabled:opacity-40",
        styles,
      ].join(" ")}
    >
      {icon}
    </button>
  );
}

export interface RoomControlBarProps {
  microphoneEnabled: boolean;
  cameraEnabled: boolean;
  speakerMuted: boolean;
  transcriptOpen: boolean;
  fullscreenActive: boolean;
  fullscreenSupported: boolean;
  /** Enabled only while the room is listening and there is something to send. */
  canFinishAnswering: boolean;
  onFinishAnswering: () => void;
  onToggleMicrophone: () => void;
  onToggleCamera: () => void;
  onToggleSpeaker: () => void;
  onToggleTranscript: () => void;
  onReplayLast: () => void;
  onEnterFullscreen: () => void;
  onEnd: () => void;
}

export function RoomControlBar({
  microphoneEnabled,
  cameraEnabled,
  speakerMuted,
  transcriptOpen,
  fullscreenActive,
  fullscreenSupported,
  canFinishAnswering,
  onFinishAnswering,
  onToggleMicrophone,
  onToggleCamera,
  onToggleSpeaker,
  onToggleTranscript,
  onReplayLast,
  onEnterFullscreen,
  onEnd,
}: RoomControlBarProps) {
  return (
    <div className="flex items-center justify-between gap-4 border-t border-[var(--room-rule)] bg-[var(--room-panel)] px-4 py-3 sm:px-6">
      <div className="flex items-center gap-2">
        <ControlButton
          onClick={onToggleMicrophone}
          label={microphoneEnabled ? "Mute microphone" : "Unmute microphone"}
          pressed={!microphoneEnabled}
          variant={microphoneEnabled ? "default" : "off"}
          icon={microphoneEnabled ? <Mic size={18} /> : <MicOff size={18} />}
        />
        <ControlButton
          onClick={onToggleCamera}
          label={cameraEnabled ? "Turn camera off" : "Turn camera on"}
          pressed={!cameraEnabled}
          variant={cameraEnabled ? "default" : "off"}
          icon={cameraEnabled ? <Video size={18} /> : <VideoOff size={18} />}
        />
        <ControlButton
          onClick={onToggleSpeaker}
          label={speakerMuted ? "Unmute the interviewer" : "Mute the interviewer"}
          pressed={speakerMuted}
          variant={speakerMuted ? "off" : "default"}
          icon={speakerMuted ? <VolumeX size={18} /> : <Volume2 size={18} />}
        />
      </div>

      <div className="flex items-center gap-2">
        {/* "Done answering" is the escape hatch from the silence timer. A
            candidate who has finished and knows it should not have to sit
            through two seconds of nothing to prove it. */}
        <button
          type="button"
          onClick={onFinishAnswering}
          disabled={!canFinishAnswering}
          className={[
            "hidden h-11 items-center gap-2 rounded-full px-5 text-sm font-medium transition-colors sm:flex",
            canFinishAnswering
              ? "bg-[var(--room-accent-dim)] text-[var(--room-accent)] hover:bg-[rgb(74_158_255/0.24)]"
              : "cursor-not-allowed bg-[var(--room-raised)] text-[var(--room-muted)] opacity-50",
          ].join(" ")}
        >
          Done answering
        </button>

        <ControlButton
          onClick={onReplayLast}
          label="Repeat the last question"
          icon={<Repeat size={18} />}
        />
        <ControlButton
          onClick={onToggleTranscript}
          label={transcriptOpen ? "Hide transcript" : "Show transcript"}
          pressed={transcriptOpen}
          icon={<FileText size={18} />}
        />
        {fullscreenSupported && !fullscreenActive ? (
          <ControlButton
            onClick={onEnterFullscreen}
            label="Return to full screen"
            icon={<Maximize2 size={18} />}
          />
        ) : null}
      </div>

      <button
        type="button"
        onClick={onEnd}
        className="flex h-11 items-center gap-2 rounded-full bg-[var(--room-danger)] px-5 text-sm font-medium text-white transition-[filter] hover:brightness-110"
      >
        <PhoneOff size={16} aria-hidden="true" />
        <span className="hidden sm:inline">End interview</span>
      </button>
    </div>
  );
}
