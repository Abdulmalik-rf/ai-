"use client";

import { Link } from "@/i18n/routing";
import { useLocale, useTranslations } from "next-intl";
import { useFormState, useFormStatus } from "react-dom";

import { signup } from "@/lib/auth";
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

export default function SignUpPage() {
  const t = useTranslations("auth.signup");
  const tErrors = useTranslations("auth.signup.errors");
  const locale = useLocale();
  const [state, formAction] = useFormState(signup, { error: null });

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
          <input type="hidden" name="locale" value={locale} />

          {errorMsg && (
            <div
              role="alert"
              className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
            >
              {errorMsg}
            </div>
          )}

          <div className="space-y-1.5">
            <label className="text-sm font-medium">{t("firmNameLabel")}</label>
            <Input name="firm_name" required />
          </div>

          <div className="space-y-1.5">
            <label className="text-sm font-medium">{t("fullNameLabel")}</label>
            <Input name="full_name" required />
          </div>

          <div className="space-y-1.5">
            <label className="text-sm font-medium">{t("emailLabel")}</label>
            <Input name="email" type="email" required autoComplete="email" />
          </div>

          <div className="space-y-1.5">
            <label className="text-sm font-medium">{t("passwordLabel")}</label>
            <Input
              name="password"
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
            />
          </div>

          <SubmitButton label={t("submit")} />
        </form>
        <p className="text-sm text-muted-foreground mt-4">
          {t("haveAccount")}{" "}
          <Link href="/sign-in" className="text-primary hover:underline">
            {t("signIn")}
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}

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
