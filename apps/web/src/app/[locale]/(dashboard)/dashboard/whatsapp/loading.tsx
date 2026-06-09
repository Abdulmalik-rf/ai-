export default function WhatsAppLoading() {
  return (
    <div className="container max-w-4xl py-8 space-y-6 animate-pulse">
      <div className="space-y-2">
        <div className="h-8 w-40 rounded-md bg-card" />
        <div className="h-4 w-1/2 rounded-md bg-card" />
      </div>
      <div className="rounded-lg border bg-card h-48" />
      <div className="rounded-lg border bg-card h-64" />
      <div className="rounded-lg border bg-card h-32" />
    </div>
  );
}
