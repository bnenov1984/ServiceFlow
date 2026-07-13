/** 4 hand-authored inline SVGs (docs/15 §6.4 "type picker 4 икони") — no icon
 * library needed for a fixed set of 4 (pragmatism directive). */

const paths: Record<string, string> = {
  phone: "M7 2h10a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1zm5 17.5a1 1 0 1 0 0 2 1 1 0 0 0 0-2z",
  vehicle:
    "M5 11l1.5-4.5A2 2 0 0 1 8.4 5h7.2a2 2 0 0 1 1.9 1.5L19 11m-14 0h14m-14 0a2 2 0 0 0-2 2v4a1 1 0 0 0 1 1h1m14-7a2 2 0 0 1 2 2v4a1 1 0 0 1-1 1h-1m-14 0a2 2 0 1 0 4 0m10 0a2 2 0 1 0 4 0m-14 0h10",
  laptop:
    "M4 5h16a1 1 0 0 1 1 1v10H3V6a1 1 0 0 1 1-1zm-2 13h20a1 1 0 0 1-1 2H3a1 1 0 0 1-1-2z",
  other:
    "M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18v3h3l6.3-6.3a4 4 0 0 0 5.4-5.4l-2.8 2.8-2-2z",
};

export function AssetTypeIcon({ code, className = "h-6 w-6" }: { code: string; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}
         strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden>
      <path d={paths[code] ?? paths.other} />
    </svg>
  );
}
