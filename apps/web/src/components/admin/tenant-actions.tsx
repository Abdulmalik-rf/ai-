"use client";

import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";

export function TenantActions({
  id,
  isActive,
  slug,
}: {
  id: string;
  isActive: boolean;
  slug: string;
}) {
  const router = useRouter();
  const isPlatform = slug === "platform";

  async function toggle() {
    if (isPlatform) return;
    const action = isActive ? "suspend" : "activate";
    const res = await fetch(`/api/v1/admin/tenants/${id}/${action}`, {
      method: "POST",
    });
    if (!res.ok) {
      alert(await res.text());
      return;
    }
    router.refresh();
  }

  return (
    <Button
      size="sm"
      variant={isActive ? "destructive" : "default"}
      onClick={toggle}
      disabled={isPlatform}
    >
      {isActive ? "Suspend" : "Activate"}
    </Button>
  );
}
