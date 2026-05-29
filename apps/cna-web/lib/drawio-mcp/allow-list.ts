// Icon library allow-list. Pinned per the Draw.io integration plan.
// To change sets, update here AND the Python client AND the build-time filter
// in scripts/filter-shape-index.mjs.

export const ALLOWED_LIBS = ["azure2", "aws4"] as const;

export type AllowedLib = (typeof ALLOWED_LIBS)[number];

const STYLE_PREFIX_RE = /^[^;]*shape=mxgraph\.([a-z0-9]+)\./i;

/** Return the icon-library prefix for a draw.io style string, or null. */
export function libOf(style: string): string | null {
  const m = style.match(STYLE_PREFIX_RE);
  return m ? m[1].toLowerCase() : null;
}

/** True iff a style string belongs to an allow-listed library. */
export function isAllowedStyle(style: string): boolean {
  const lib = libOf(style);
  return lib !== null && (ALLOWED_LIBS as readonly string[]).includes(lib);
}
