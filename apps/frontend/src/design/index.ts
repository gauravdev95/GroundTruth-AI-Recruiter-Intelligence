/**
 * The design-system barrel. `components/index.ts` is the export surface most
 * screens use; this one exists for the pieces that are not components —
 * motion tokens and hooks, the theme hook — so a screen imports the system
 * from one place instead of memorising which file each hook lives in.
 */
export { Backdrop, Surface } from "./Surface";
export {
  Celebrate,
  ProgressRing,
  Reveal,
  Shake,
  Stagger,
  Transition,
} from "./primitives";
export {
  DURATION,
  EASE,
  SPRING,
  SPRING_TRAVEL,
  STAGGER,
  TRAVEL,
  prefersReducedMotion,
  subscribeFrame,
  useAfterIdle,
  useCountUp,
  useInViewShared,
  useIsNarrow,
  useIsTablet,
  useIsTouch,
  useMagnetic,
  useReducedMotionSafe,
  useSequence,
} from "./motion";
export {
  applyTheme,
  resolveTheme,
  useTheme,
  type ResolvedTheme,
  type ThemeChoice,
  type UseThemeResult,
} from "./theme";
