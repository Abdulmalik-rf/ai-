import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DatasetUploader } from "@/components/admin/dataset-uploader";

export default function DatasetsPage() {
  return (
    <div className="container py-8 space-y-6">
      <h1 className="text-3xl font-bold tracking-tight">Saudi-law datasets</h1>
      <p className="text-muted-foreground">
        Upload base statutes (e.g., Companies Law, Labor Law). Uploaded
        documents are owned by the platform tenant and visible to every law
        firm via the RAG retrieval layer.
      </p>

      <Card>
        <CardHeader>
          <CardTitle>Upload</CardTitle>
        </CardHeader>
        <CardContent>
          <DatasetUploader />
        </CardContent>
      </Card>
    </div>
  );
}
