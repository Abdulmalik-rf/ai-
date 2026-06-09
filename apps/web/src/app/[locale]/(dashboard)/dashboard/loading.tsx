/**
 * Default loading state for any /dashboard/* route that doesn't ship its own
 * loading.tsx. Next.js shows this between the click and the new route's RSC
 * streaming — replaces the "nothing happens" feel during navigation.
 */
export default function DashboardLoading() {
  return (
    <div className="container py-8 space-y-6 animate-pulse">
      <div className="flex items-center justify-between gap-4">
        <div className="h-9 w-48 rounded-md bg-card" />
        <div className="h-9 w-32 rounded-md bg-card" />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="rounded-lg border bg-card h-32" />
        ))}
      </div>
    </div>
  );
}
