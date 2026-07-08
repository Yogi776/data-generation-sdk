"use client";

import { Database, RefreshCw, Terminal } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import {
  EmptyState,
  ErrorState,
  LoadingRows,
  Spinner,
} from "@/components/shared/states";
import { CodeBlock } from "@/components/shared/code-block";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useScan, useSources } from "@/lib/api/hooks";
import { formatDate, formatNumber } from "@/lib/utils";

const CONNECT_HINT = `# Connect a source, then scan
adp connect --name sales --type csv --path ./data
adp scan`;

export default function SourcesPage() {
  const { data, isLoading, isError, refetch } = useSources();
  const scan = useScan();

  return (
    <>
      <PageHeader
        title="Sources"
        description="Data sources configured in adp.yaml. Credentials are never stored here — they resolve from the environment."
        actions={
          <Button
            onClick={() => scan.mutate()}
            disabled={scan.isPending || (data?.length ?? 0) === 0}
          >
            {scan.isPending ? <Spinner /> : <RefreshCw />}
            Scan
          </Button>
        }
      />

      {isError ? (
        <ErrorState onRetry={refetch} />
      ) : isLoading ? (
        <LoadingRows />
      ) : (data?.length ?? 0) === 0 ? (
        <div className="space-y-4">
          <EmptyState
            icon={Database}
            title="No sources configured"
            description="Sources are added from the CLI. Once connected, they'll show up here and you can scan them into the catalog."
          />
          <Card>
            <CardContent className="p-4">
              <div className="mb-2 flex items-center gap-2 text-sm font-medium">
                <Terminal className="h-4 w-4" /> Add your first source
              </div>
              <CodeBlock code={CONNECT_HINT} language="bash" />
            </CardContent>
          </Card>
        </div>
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Type</TableHead>
                <TableHead className="text-right">Tables</TableHead>
                <TableHead>Last scanned</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data!.map((s) => (
                <TableRow key={s.name}>
                  <TableCell className="font-medium">{s.name}</TableCell>
                  <TableCell>
                    <Badge variant="secondary">{s.type}</Badge>
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {formatNumber(s.tables)}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatDate(s.last_scanned_at)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
    </>
  );
}
