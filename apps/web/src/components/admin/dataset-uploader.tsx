"use client";

import { useRef, useState } from "react";
import { Loader2, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function DatasetUploader() {
  const [title, setTitle] = useState("");
  const [language, setLanguage] = useState("ar");
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const file = inputRef.current?.files?.[0];
    if (!file) return;
    setUploading(true);
    setSuccess(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("title", title || file.name);
      fd.append("language", language);
      const res = await fetch("/api/v1/admin/datasets", {
        method: "POST",
        body: fd,
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setSuccess(`Queued: ${data.document_id}`);
      setTitle("");
      if (inputRef.current) inputRef.current.value = "";
    } catch (err) {
      alert((err as Error).message);
    } finally {
      setUploading(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="space-y-1.5">
        <label className="text-sm font-medium">Title</label>
        <Input value={title} onChange={(e) => setTitle(e.target.value)} />
      </div>

      <div className="space-y-1.5">
        <label className="text-sm font-medium">Language</label>
        <select
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          className="w-full rounded-md border border-input bg-background h-10 px-3 text-sm"
        >
          <option value="ar">Arabic</option>
          <option value="en">English</option>
        </select>
      </div>

      <div className="space-y-1.5">
        <label className="text-sm font-medium">File</label>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,.txt"
          required
          className="block w-full text-sm"
        />
      </div>

      <Button type="submit" disabled={uploading}>
        {uploading ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Upload className="h-4 w-4" />
        )}
        Upload
      </Button>
      {success && <div className="text-sm text-emerald-600">{success}</div>}
    </form>
  );
}
