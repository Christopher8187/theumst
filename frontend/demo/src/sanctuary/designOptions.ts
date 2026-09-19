// Six studies on the existing DEV-only route. Brief and action placement are independent.
export const variants = ['A', 'B', 'C', 'D', 'E', 'F'] as const;
export type Variant = typeof variants[number];
export type BriefDesign = 'A' | 'B' | 'C';
export type ActionPlacement = 'D' | 'E' | 'F';
export const designNames: Record<Variant, string> = {
  A: 'folio', B: 'contentsBeside', C: 'sidePanel',
  D: 'topMenu', E: 'sideRail', F: 'bottomDock',
};
export const acrossActions = [
  { id: 'review', symbol: '覺', description: 'acrossReview' },
  { id: 'advice', symbol: '意', description: 'acrossAdvice' },
  { id: 'expand', symbol: '道', description: 'acrossExpand' },
  { id: 'progress', symbol: '境', description: 'acrossProgress' },
] as const;
