export default function SettingsLoading() {
  return (
    <div className="container max-w-3xl py-8 space-y-6 animate-pulse">
      <div className="space-y-1">
        <div className="h-9 w-40 rounded-md bg-card" />
        <div className="h-4 w-2/3 rounded-md bg-card" />
      </div>
      <div className="space-y-6">
        <div className="rounded-lg border bg-card h-56" />
        <div className="rounded-lg border bg-card h-56" />
        <div className="rounded-lg border bg-card h-40" />
      </div>
    </div>
  );
}
