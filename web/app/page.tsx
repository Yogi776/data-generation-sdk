"use client";

import Link from "next/link";
import {
  ArrowRight,
  Boxes,
  Database,
  RefreshCw,
  Table2,
} from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { StatCard } from "@/components/shared/stat-card";
import { EmptyState, ErrorState, LoadingRows } from "@/components/shared/states";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Spinner } from "@/components/shared/states";
import { NAV } from "@/lib/nav";
import { useScan, useSources, useTables } from "@/lib/api/hooks";
import { formatNumber } from "@/lib/utils";

export default function OverviewPage() {
  const sources = useSources();
  const tables = useTables();
  const scan = useScan();

  const totalRows =
    tables.data?.reduce((n, t) => n + (t.row_count ?? 0), 0) ?? 0;
  const totalColumns =
    tables.data?.reduce((n, t) => n + (t.columns ?? 0), 0) ?? 0;

  if (sources.isError || tables.isError) {
    return (
      <>
        <PageHeader title="Overview" />
        <ErrorState onRetry={() => tables.refetch()} />
      </>
    );
  }

  const empty =
    !sources.isLoading &&
    !tables.isLoading &&
    (sources.data?.length ?? 0) === 0;

  return (
    <>
      <PageHeader
        title="Overview"
        description="Everything the platform has learned about your project."
        actions={
          <Button
            onClick={() => scan.mutate()}
            disabled={scan.isPending || (sources.data?.length ?? 0) === 0}
          >
            {scan.isPending ? <Spinner /> : <RefreshCw />}
            Re-scan sources
          </Button>
        }
      />

      {empty ? (
        <EmptyState
          icon={Database}
          title="No sources connected yet"
          description="Connect a source from the CLI (adp connect …), then scan to build the catalog."
          action={
            <Button variant="outline" asChild>
              <Link href="/sources">Go to sources</Link>
            </Button>
          }
        />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            {sources.isLoading || tables.isLoading ? (
              <div className="sm:col-span-3">
                <LoadingRows rows={1} />
              </div>
            ) : (
              <>
                <StatCard
                  label="Sources"
                  value={formatNumber(sources.data?.length ?? 0)}
                  icon={Database}
                />
                <StatCard
                  label="Tables"
                  value={formatNumber(tables.data?.length ?? 0)}
                  hint={`${formatNumber(totalColumns)} columns`}
                  icon={Table2}
                />
                <StatCard
                  label="Source rows"
                  value={formatNumber(totalRows)}
                  icon={Boxes}
                />
              </>
            )}
          </div>

          <div className="mt-8">
            <h3 className="mb-3 text-sm font-semibold text-muted-foreground">
              Workflow
            </h3>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {NAV.filter((n) => n.href !== "/").map((item) => {
                const Icon = item.icon;
                return (
                  <Link key={item.href} href={item.href}>
                    <Card className="group h-full transition-colors hover:border-primary/40 hover:bg-accent/40">
                      <CardHeader className="pb-3">
                        <div className="mb-1 flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                          <Icon className="h-4 w-4" />
                        </div>
                        <CardTitle className="flex items-center gap-1 text-base">
                          {item.label}
                          <ArrowRight className="h-3.5 w-3.5 opacity-0 transition-opacity group-hover:opacity-100" />
                        </CardTitle>
                        <CardDescription>{item.description}</CardDescription>
                      </CardHeader>
                    </Card>
                  </Link>
                );
              })}
            </div>
          </div>
        </>
      )}
    </>
  );
}
