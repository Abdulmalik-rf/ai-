export default function CaseDetailLoading() {
  return (
    <div className="container py-8 space-y-6 animate-pulse">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2 flex-1 min-w-0">
          <div className="h-4 w-32 rounded-md bg-card" />
          <div className="h-9 w-2/3 rounded-md bg-card" />
          <div className="flex gap-2">
            <div className="h-6 w-20 rounded-md bg-card" />
            <div className="h-6 w-20 rounded-md bg-card" />
          </div>
        </div>
        <div className="h-9 w-32 rounded-md bg-card shrink-0" />
      </div>
      <div className="rounded-lg border bg-card h-64" />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="rounded-lg border bg-card h-48" />
        <div className="rounded-lg border bg-card h-48" />
      </div>
    </div>
  );
}
