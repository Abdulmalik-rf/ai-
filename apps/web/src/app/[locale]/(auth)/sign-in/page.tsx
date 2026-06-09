"use client";

import { Link } from "@/i18n/routing";
import { useTranslations } from "next-intl";
import { useFormState, useFormStatus } from "react-dom";

import { login } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

function SubmitButton({ label }: { label: string }) {
  const { pending } = useFormStatus();
  return (
    <Button type="submit" className="w-full" disabled={pending}>
      {pending ? "…" : label}
    </Button>
  );
}

export default function SignInPage() {
  const t = useTranslations("auth.signin");
  const tErrors = useTranslations("auth.signin.errors");
  const [state, formAction] = useFormState(login, { error: null });

  // The server action returns a stable error CODE (e.g. "wrong_credentials")
  // or "raw:<message>" for unexpected upstream errors. Translate codes via
  // i18n; render raw passthroughs verbatim.
  const errorMsg = state.error
    ? state.error.startsWith("raw:")
      ? state.error.slice(4)
      : safeTranslate(tErrors, state.error)
    : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("title")}</CardTitle>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
      </CardHeader>
      <CardContent>
        <form action={formAction} className="space-y-4">
          {errorMsg && (
            <div
              role="alert"
              className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
            >
              {errorMsg}
            </div>
          )}
          <div className="space-y-1.5">
            <label className="text-sm font-medium" htmlFor="email">
              {t("emailLabel")}
            </label>
            <Input
              id="email"
              name="email"
              type="email"
              required
              autoComplete="email"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium" htmlFor="password">
              {t("passwordLabel")}
            </label>
            <Input
              id="password"
              name="password"
              type="password"
              required
              autoComplete="current-password"
            />
          </div>
          <SubmitButton label={t("submit")} />
        </form>
        <p className="text-sm text-muted-foreground mt-4">
          {t("noAccount")}{" "}
          <Link href="/sign-up" className="text-primary hover:underline">
            {t("createAccount")}
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}

/** Look up an i18n key; if the key isn't defined, return the raw code so
 *  the user still sees something instead of next-intl throwing. */
function safeTranslate(
  t: ReturnType<typeof useTranslations>,
  key: string,
): string {
  try {
    return t(key);
  } catch {
    return key;
  }
}
