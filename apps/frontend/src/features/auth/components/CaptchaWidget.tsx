import { useEffect, useId, useRef } from "react";

interface GrecaptchaApi {
  render: (container: HTMLElement, params: Record<string, unknown>) => number;
  reset: (widgetId?: number) => void;
}

declare global {
  interface Window {
    grecaptcha?: GrecaptchaApi;
    __gtRecaptchaOnLoad?: () => void;
  }
}

let scriptLoadPromise: Promise<void> | null = null;

function loadRecaptchaScript(): Promise<void> {
  if (window.grecaptcha) return Promise.resolve();
  if (scriptLoadPromise) return scriptLoadPromise;

  scriptLoadPromise = new Promise((resolve) => {
    window.__gtRecaptchaOnLoad = () => resolve();
    const script = document.createElement("script");
    script.src = "https://www.google.com/recaptcha/api.js?onload=__gtRecaptchaOnLoad&render=explicit";
    script.async = true;
    script.defer = true;
    document.head.appendChild(script);
  });
  return scriptLoadPromise;
}

interface CaptchaWidgetProps {
  onChange: (token: string | null) => void;
  error?: string;
}

/**
 * reCAPTCHA v2 checkbox, loaded via Google's <script> tag (there's no
 * first-party npm package for this — that's the standard integration
 * path). When VITE_RECAPTCHA_SITE_KEY isn't set, this renders a notice
 * and reports a placeholder token so the form stays usable in
 * development — the backend independently gates its own bypass on
 * APP_ENV=development, so this never weakens production.
 */
export function CaptchaWidget({ onChange, error }: CaptchaWidgetProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const widgetIdRef = useRef<number | null>(null);
  const id = useId();
  const siteKey = import.meta.env.VITE_RECAPTCHA_SITE_KEY as string | undefined;

  useEffect(() => {
    if (!siteKey) {
      onChange("dev-bypass");
      return;
    }

    let cancelled = false;
    void loadRecaptchaScript().then(() => {
      if (cancelled || !containerRef.current || widgetIdRef.current !== null || !window.grecaptcha) return;
      widgetIdRef.current = window.grecaptcha.render(containerRef.current, {
        sitekey: siteKey,
        callback: (token: string) => onChange(token),
        "expired-callback": () => onChange(null),
        "error-callback": () => onChange(null),
      });
    });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [siteKey]);

  if (!siteKey) {
    return (
      <div className="rounded-xl border border-dashed border-amber-400/40 bg-amber-400/10 px-4 py-3 text-xs text-amber-300">
        CAPTCHA isn't configured for this environment — verification is skipped in development.
      </div>
    );
  }

  return (
    <div>
      <div id={id} ref={containerRef} />
      {error ? (
        <p role="alert" className="mt-1 text-xs text-red-400">
          {error}
        </p>
      ) : null}
    </div>
  );
}
