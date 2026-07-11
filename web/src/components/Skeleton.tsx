/** Skeleton loading placeholders for async page loading states. */

interface SkeletonProps {
  /** Number of skeleton cards/rows to render (default 1). */
  count?: number;
}

/** A card-sized skeleton block, matching the .card shape. */
export function SkeletonCard({ count = 1 }: SkeletonProps) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="skeleton skeleton-card" />
      ))}
    </>
  );
}

/** A smaller card skeleton (e.g. for settings page groups). */
export function SkeletonCardSm({ count = 1 }: SkeletonProps) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="skeleton skeleton-card-sm" />
      ))}
    </>
  );
}

/** A row with an avatar circle on the left and text lines on the right. */
export function SkeletonRow({ count = 1 }: SkeletonProps) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="skeleton-row">
          <div className="skeleton skeleton-avatar" />
          <div className="skeleton-lines">
            <div className="skeleton skeleton-text" style={{ width: "35%" }} />
            <div className="skeleton skeleton-text" />
            <div className="skeleton skeleton-text" style={{ width: "55%" }} />
          </div>
        </div>
      ))}
    </>
  );
}

/** A title + several text lines (for page header placeholders). */
export function SkeletonPage() {
  return (
    <div style={{ padding: "4px 0" }}>
      <div className="skeleton skeleton-title" />
      <div className="skeleton skeleton-text" />
      <div className="skeleton skeleton-text" style={{ width: "75%" }} />
      <div style={{ marginTop: 24 }}>
        <SkeletonCard count={3} />
      </div>
    </div>
  );
}

/** A grid of skeleton cards (for skill grid layout). */
export function SkeletonGrid({ count = 6 }: { count?: number }) {
  return (
    <div className="skill-grid">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="skeleton" style={{ height: 140, borderRadius: "var(--radius-lg)" }} />
      ))}
    </div>
  );
}
