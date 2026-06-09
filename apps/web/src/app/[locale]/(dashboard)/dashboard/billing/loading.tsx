export default function BillingLoading() {
  return (
    <div className="container py-8 space-y-6 animate-pulse">
      <div className="h-9 w-40 rounded-md bg-card" />
      <div className="space-y-4">
        <div className="rounded-lg border bg-card h-32" />
        <div className="rounded-lg border bg-card h-48" />
      </div>
    </div>
  );
}
