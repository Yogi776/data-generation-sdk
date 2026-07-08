"use client";

import { usePathname } from "next/navigation";
import { NAV } from "@/lib/nav";
import { useHealth } from "@/lib/api/hooks";
import { ThemeToggle } from "./theme-toggle";
import { cn } from "@/lib/utils";

export function Header() {
  const pathname = usePathname();
  const current =
    NAV.find((n) =>
      n.href === "/" ? pathname === "/" : pathname.startsWith(n.href)
    ) ?? NAV[0];
  const { data, isError, isLoading } = useHealth();

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between gap-4 border-b bg-background/80 px-6 backdrop-blur lg:px-10">
      <div className="min-w-0">
        <h1 className="truncate text-sm font-semibold">{current.label}</h1>
        <p className="truncate text-xs text-muted-foreground">
          {current.description}
        </p>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span
            className={cn(
              "h-2 w-2 rounded-full",
              isLoading
                ? "bg-warning animate-pulse"
                : isError
                  ? "bg-destructive"
                  : "bg-success"
            )}
          />
          <span className="hidden sm:inline">
            {isLoading
              ? "connecting…"
              : isError
                ? "backend offline"
                : `API v${data?.version ?? "?"}`}
          </span>
        </div>
        <ThemeToggle />
      </div>
    </header>
  );
}
