export default function CasesLoading() {
  return (
    <div className="container py-8 space-y-6 animate-pulse">
      <div className="flex items-center justify-between gap-4">
        <div className="h-9 w-40 rounded-md bg-card" />
        <div className="h-9 w-32 rounded-md bg-card" />
      </div>
      <div className="space-y-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-lg border bg-card h-28" />
        ))}
      </div>
    </div>
  );
}
