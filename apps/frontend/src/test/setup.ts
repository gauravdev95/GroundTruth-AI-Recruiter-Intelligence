import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

// Testing Library's auto-cleanup only registers itself when a global `afterEach`
// exists at import time; registering it explicitly keeps it working regardless
// of how `globals` is configured.
afterEach(() => {
  cleanup();
});

/**
 * jsdom implements neither of these, and both are called during render by
 * components this suite mounts — `matchMedia` by responsive helpers,
 * `scrollTo` by the router's scroll reset. Left undefined they throw, which
 * would fail tests for a reason that has nothing to do with what they assert.
 */
if (!window.matchMedia) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

window.scrollTo = vi.fn();
