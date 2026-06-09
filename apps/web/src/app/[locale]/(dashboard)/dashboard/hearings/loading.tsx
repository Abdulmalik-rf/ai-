export default function HearingsLoading() {
  return (
    <div className="container py-8 space-y-6 animate-pulse">
      <div className="h-9 w-40 rounded-md bg-card" />
      <div className="rounded-lg border bg-card h-12" />
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="rounded-lg border bg-card h-20" />
        ))}
      </div>
    </div>
  );
}
