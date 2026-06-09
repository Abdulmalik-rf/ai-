import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-primary text-primary-foreground",
        secondary:
          "border-transparent bg-secondary text-secondary-foreground",
        outline: "text-foreground",
        info:
          "border-transparent bg-blue-100 text-blue-900 dark:bg-blue-900/30 dark:text-blue-200",
        success:
          "border-transparent bg-emerald-100 text-emerald-900 dark:bg-emerald-900/30 dark:text-emerald-200",
        warning:
          "border-transparent bg-amber-100 text-amber-900 dark:bg-amber-900/30 dark:text-amber-200",
        destructive:
          "border-transparent bg-rose-100 text-rose-900 dark:bg-rose-900/30 dark:text-rose-200",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

export const Badge = ({ className, variant, ...props }: BadgeProps) => (
  <div className={cn(badgeVariants({ variant }), className)} {...props} />
);
