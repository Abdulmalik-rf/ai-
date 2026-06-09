export default function StaffLoading() {
  return (
    <div className="container py-8 space-y-6 animate-pulse">
      <div className="space-y-1">
        <div className="h-9 w-40 rounded-md bg-card" />
        <div className="h-4 w-2/3 rounded-md bg-card" />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="rounded-lg border bg-card h-48" />
        ))}
      </div>
    </div>
  );
}
