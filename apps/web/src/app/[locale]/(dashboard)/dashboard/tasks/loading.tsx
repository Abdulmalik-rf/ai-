export default function TasksLoading() {
  return (
    <div className="container py-8 space-y-6 animate-pulse">
      <div className="h-9 w-40 rounded-md bg-card" />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="rounded-lg border bg-card h-64" />
        ))}
      </div>
    </div>
  );
}
