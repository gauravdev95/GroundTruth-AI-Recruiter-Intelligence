import { useEffect, useRef, useState } from "react";
import type { ClipboardEvent, KeyboardEvent } from "react";

interface OtpInputProps {
  length?: number;
  onComplete: (otp: string) => void;
  onResend: () => void;
  resendCooldownSeconds: number;
  isResending?: boolean;
  disabled?: boolean;
}

export function OtpInput({
  length = 6,
  onComplete,
  onResend,
  resendCooldownSeconds,
  isResending = false,
  disabled = false,
}: OtpInputProps) {
  const [digits, setDigits] = useState<string[]>(() => Array(length).fill(""));
  const [secondsLeft, setSecondsLeft] = useState(resendCooldownSeconds);
  const inputsRef = useRef<Array<HTMLInputElement | null>>([]);

  useEffect(() => {
    setSecondsLeft(resendCooldownSeconds);
  }, [resendCooldownSeconds]);

  useEffect(() => {
    if (secondsLeft <= 0) return;
    const timer = window.setInterval(() => setSecondsLeft((s) => Math.max(0, s - 1)), 1000);
    return () => window.clearInterval(timer);
  }, [secondsLeft]);

  const handleChange = (index: number, rawValue: string) => {
    const clean = rawValue.replace(/\D/g, "").slice(-1);
    const next = [...digits];
    next[index] = clean;
    setDigits(next);

    if (clean && index < length - 1) {
      inputsRef.current[index + 1]?.focus();
    }
    if (next.every((d) => d !== "")) {
      onComplete(next.join(""));
    }
  };

  const handleKeyDown = (index: number, e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Backspace" && !digits[index] && index > 0) {
      inputsRef.current[index - 1]?.focus();
    }
  };

  const handlePaste = (e: ClipboardEvent<HTMLInputElement>) => {
    const pasted = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, length);
    if (!pasted) return;
    e.preventDefault();
    const next = Array(length).fill("");
    pasted.split("").forEach((char, i) => {
      next[i] = char;
    });
    setDigits(next);
    if (pasted.length === length) {
      onComplete(pasted);
    } else {
      inputsRef.current[pasted.length]?.focus();
    }
  };

  const handleResend = () => {
    onResend();
    setSecondsLeft(resendCooldownSeconds);
    setDigits(Array(length).fill(""));
    inputsRef.current[0]?.focus();
  };

  return (
    <div className="flex flex-col items-center gap-4">
      <div className="flex gap-2 sm:gap-3" role="group" aria-label="Verification code">
        {digits.map((digit, index) => (
          <input
            key={index}
            ref={(el) => {
              inputsRef.current[index] = el;
            }}
            type="text"
            inputMode="numeric"
            autoComplete={index === 0 ? "one-time-code" : "off"}
            maxLength={1}
            value={digit}
            disabled={disabled}
            onChange={(e) => handleChange(index, e.target.value)}
            onKeyDown={(e) => handleKeyDown(index, e)}
            onPaste={handlePaste}
            aria-label={`Digit ${index + 1} of ${length}`}
            className="h-12 w-10 rounded border border-slate-300 bg-white text-center text-lg font-semibold text-slate-900 outline-none transition focus:border-ink focus:ring-2 focus:ring-verified/25 sm:h-14 sm:w-12"
          />
        ))}
      </div>
      <button
        type="button"
        onClick={handleResend}
        disabled={secondsLeft > 0 || isResending || disabled}
        className="text-sm font-medium text-ink underline decoration-rule underline-offset-2 transition hover:decoration-ink disabled:cursor-not-allowed disabled:text-slate-300"
      >
        {secondsLeft > 0 ? `Resend code in ${secondsLeft}s` : isResending ? "Sending…" : "Resend code"}
      </button>
    </div>
  );
}
