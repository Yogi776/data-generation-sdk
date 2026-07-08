import { KeyRound, ShieldAlert } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

export function PiiBadge({ level }: { level: string | null }) {
  if (!level || level === "none") return null;
  return (
    <Badge variant="warning" className="gap-1">
      <ShieldAlert className="h-3 w-3" />
      PII{level && level !== "pii" ? `: ${level}` : ""}
    </Badge>
  );
}

export function PkBadge() {
  return (
    <Badge variant="default" className="gap-1">
      <KeyRound className="h-3 w-3" />
      PK
    </Badge>
  );
}

export function KindBadge({ kind }: { kind: string }) {
  const variant =
    kind === "fact" ? "default" : kind === "dimension" ? "secondary" : "muted";
  return <Badge variant={variant}>{kind}</Badge>;
}

export function ConfidenceBadge({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const variant = value >= 0.8 ? "success" : value >= 0.6 ? "warning" : "muted";
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span>
          <Badge variant={variant}>{pct}%</Badge>
        </span>
      </TooltipTrigger>
      <TooltipContent>Inference confidence</TooltipContent>
    </Tooltip>
  );
}
