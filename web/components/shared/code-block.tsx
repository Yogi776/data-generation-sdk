"use client";

import * as React from "react";
import { Check, Copy } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function CodeBlock({
  code,
  language,
  className,
  maxHeight = 420,
}: {
  code: string;
  language?: string;
  className?: string;
  maxHeight?: number;
}) {
  const [copied, setCopied] = React.useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      toast.success("Copied to clipboard");
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error("Copy failed");
    }
  }

  return (
    <div className={cn("relative rounded-lg border bg-muted/40", className)}>
      {language ? (
        <div className="flex items-center justify-between border-b px-3 py-1.5">
          <span className="text-[11px] uppercase tracking-wide text-muted-foreground">
            {language}
          </span>
        </div>
      ) : null}
      <Button
        variant="ghost"
        size="icon"
        className="absolute right-2 top-2 h-7 w-7"
        onClick={copy}
        aria-label="Copy"
      >
        {copied ? (
          <Check className="h-3.5 w-3.5 text-success" />
        ) : (
          <Copy className="h-3.5 w-3.5" />
        )}
      </Button>
      <pre
        className="overflow-auto p-4 font-mono text-xs leading-relaxed scrollbar-thin"
        style={{ maxHeight }}
      >
        <code>{code}</code>
      </pre>
    </div>
  );
}
