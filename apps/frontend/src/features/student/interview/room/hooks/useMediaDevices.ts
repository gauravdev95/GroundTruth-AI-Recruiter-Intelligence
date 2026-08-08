import { useCallback, useEffect, useRef, useState } from "react";

/**
 * The candidate's camera and microphone.
 *
 * ## There is no peer connection, and that is deliberate
 *
 * A video call normally means WebRTC because there is someone on the other end.
 * Here there is not: the interviewer is an avatar rendered locally and a voice
 * synthesised locally, so there is no remote track to negotiate, no SFU, no
 * signalling. What the room needs from the media stack is exactly what
 * `getUserMedia` gives it — a local preview, a microphone the recogniser can
 * read, and honest device state.
 *
 * The consequence is the privacy property worth stating out loud: **the video
 * never leaves the machine.** No frame is uploaded, nothing is recorded, and
 * there is no code path in this room that could do either. The only thing that
 * reaches the server is text, on the same interview API the typed interview
 * used.
 *
 * ## Camera and microphone are acquired separately
 *
 * One `getUserMedia({ video: true, audio: true })` call fails as a unit — a
 * candidate with a broken webcam and a working headset gets nothing, and the
 * error tells them neither which device failed nor that the other one was fine.
 * Two calls cost one extra permission prompt and buy a room that can say
 * "your microphone is fine, your camera isn't" and carry on.
 */

export type PermissionState = "idle" | "prompting" | "granted" | "denied" | "unavailable";

export interface DeviceState {
  camera: PermissionState;
  microphone: PermissionState;
  /** Set when a device that was working stopped — unplugged, claimed by another
   * app, or revoked mid-interview. Distinct from `denied`, which is a decision
   * the candidate made before starting. */
  cameraLost: boolean;
  microphoneLost: boolean;
}

export interface MediaDevicesState extends DeviceState {
  stream: MediaStream | null;
  audioStream: MediaStream | null;
  /** The device the browser actually opened, as the OS names it. Surfaced
   * because "which microphone is this even using" is unanswerable from inside
   * the page otherwise — and on a machine with a virtual audio cable installed,
   * the answer is routinely not the one the candidate assumes. */
  audioDeviceLabel: string | null;
  cameraEnabled: boolean;
  microphoneEnabled: boolean;
  /** Human-readable reason the last acquisition failed, if it did. */
  error: string | null;
  request: () => Promise<void>;
  setCameraEnabled: (enabled: boolean) => void;
  setMicrophoneEnabled: (enabled: boolean) => void;
  release: () => void;
}

/** `NotAllowedError` is a refusal; everything else is the device or the
 * browser failing, and the two need different words in front of a candidate who
 * is about to be interviewed. */
function classify(error: unknown): { state: PermissionState; message: string } {
  const name = error instanceof Error ? error.name : "";
  switch (name) {
    case "NotAllowedError":
    case "SecurityError":
      return { state: "denied", message: "Permission was declined." };
    case "NotFoundError":
    case "OverconstrainedError":
      return { state: "unavailable", message: "No device of that kind was found." };
    case "NotReadableError":
      return {
        state: "unavailable",
        message: "The device is in use by another application.",
      };
    default:
      return { state: "unavailable", message: "The device could not be opened." };
  }
}

const VIDEO_CONSTRAINTS: MediaTrackConstraints = {
  width: { ideal: 640 },
  height: { ideal: 480 },
  facingMode: "user",
};

const AUDIO_CONSTRAINTS: MediaTrackConstraints = {
  // All three on: the recogniser is reading a laptop microphone in a room with
  // a speaker playing the interviewer's voice, which is the exact case echo
  // cancellation exists for.
  echoCancellation: true,
  noiseSuppression: true,
  autoGainControl: true,
};

export function useMediaDevices(): MediaDevicesState {
  const [camera, setCamera] = useState<PermissionState>("idle");
  const [microphone, setMicrophone] = useState<PermissionState>("idle");
  const [cameraLost, setCameraLost] = useState(false);
  const [microphoneLost, setMicrophoneLost] = useState(false);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [audioStream, setAudioStream] = useState<MediaStream | null>(null);
  const [audioDeviceLabel, setAudioDeviceLabel] = useState<string | null>(null);
  const [cameraEnabled, setCameraEnabledState] = useState(true);
  const [microphoneEnabled, setMicrophoneEnabledState] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const videoStreamRef = useRef<MediaStream | null>(null);
  const audioStreamRef = useRef<MediaStream | null>(null);

  const release = useCallback(() => {
    videoStreamRef.current?.getTracks().forEach((track) => track.stop());
    audioStreamRef.current?.getTracks().forEach((track) => track.stop());
    videoStreamRef.current = null;
    audioStreamRef.current = null;
    setStream(null);
    setAudioStream(null);
    setAudioDeviceLabel(null);
  }, []);

  const request = useCallback(async () => {
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setCamera("unavailable");
      setMicrophone("unavailable");
      setError("This browser cannot open a camera or microphone.");
      return;
    }

    setError(null);
    setCamera((current) => (current === "granted" ? current : "prompting"));
    setMicrophone((current) => (current === "granted" ? current : "prompting"));

    // Microphone first. It is the one the interview cannot run without — a
    // candidate with no camera can still be interviewed, a candidate with no
    // microphone cannot speak — so if only one prompt gets answered, this is
    // the one worth having answered.
    try {
      const mic = await navigator.mediaDevices.getUserMedia({ audio: AUDIO_CONSTRAINTS });
      audioStreamRef.current = mic;
      setAudioStream(mic);
      setMicrophone("granted");
      setMicrophoneLost(false);
      setAudioDeviceLabel(mic.getAudioTracks()[0]?.label ?? null);
      mic.getAudioTracks().forEach((track) => {
        track.onended = () => setMicrophoneLost(true);
      });
    } catch (micError) {
      const { state, message } = classify(micError);
      setMicrophone(state);
      setError(`Microphone: ${message}`);
    }

    try {
      const video = await navigator.mediaDevices.getUserMedia({ video: VIDEO_CONSTRAINTS });
      videoStreamRef.current = video;
      setStream(video);
      setCamera("granted");
      setCameraLost(false);
      video.getVideoTracks().forEach((track) => {
        track.onended = () => setCameraLost(true);
      });
    } catch (cameraError) {
      const { state, message } = classify(cameraError);
      setCamera(state);
      // Only report the camera failure if the microphone succeeded — otherwise
      // the microphone message is the one that matters and this would replace
      // it with the less important of the two.
      setError((current) => current ?? `Camera: ${message}`);
    }
  }, []);

  const setCameraEnabled = useCallback((enabled: boolean) => {
    setCameraEnabledState(enabled);
    // Disable the track rather than stopping it. Stopping releases the device,
    // which drops the browser's camera indicator and then needs a fresh
    // permission-shaped acquisition to come back — a toggle that sometimes
    // re-prompts is a toggle candidates stop trusting mid-interview.
    videoStreamRef.current?.getVideoTracks().forEach((track) => {
      track.enabled = enabled;
    });
  }, []);

  const setMicrophoneEnabled = useCallback((enabled: boolean) => {
    setMicrophoneEnabledState(enabled);
    audioStreamRef.current?.getAudioTracks().forEach((track) => {
      track.enabled = enabled;
    });
  }, []);

  useEffect(() => release, [release]);

  return {
    camera,
    microphone,
    cameraLost,
    microphoneLost,
    stream,
    audioStream,
    audioDeviceLabel,
    cameraEnabled,
    microphoneEnabled,
    error,
    request,
    setCameraEnabled,
    setMicrophoneEnabled,
    release,
  };
}
