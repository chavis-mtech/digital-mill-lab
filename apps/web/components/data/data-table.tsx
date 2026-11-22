"use client";

import { useMemo, useState, type ReactNode } from "react";
import {
  columnFilteringFeature,
  createFilteredRowModel,
  createPaginatedRowModel,
  createSortedRowModel,
  filterFn_includesString,
  globalFilteringFeature,
  rowPaginationFeature,
  rowSortingFeature,
  sortFn_alphanumeric,
  sortFn_basic,
  tableFeatures,
  useTable,
  type ColumnDef,
  type RowData,
  type SortingState,
} from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight, Download, Rows3, Rows4, Search } from "lucide-react";
import { useT } from "@/lib/i18n/client";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { EmptyState, ErrorState } from "@/components/states/states";
import common from "@/messages/common.i18n";

/**
 * App-level column definition (kept independent of TanStack's generics so pages stay simple).
 * `value` drives sorting, search and CSV; `cell` only drives rendering.
 */
export type DataTableColumn<T> = {
  id: string;
  header: string;
  value: (row: T) => string | number | null | undefined;
  cell?: (row: T) => ReactNode;
  align?: "left" | "right" | "center";
  sortable?: boolean;
  /** Exclude from global search. */
  searchable?: boolean;
  /** Exclude from CSV export. */
  csv?: boolean;
  className?: string;
};

const features = tableFeatures({
  rowSortingFeature,
  columnFilteringFeature,
  globalFilteringFeature,
  rowPaginationFeature,
  sortedRowModel: createSortedRowModel(),
  filteredRowModel: createFilteredRowModel(),
  paginatedRowModel: createPaginatedRowModel(),
  sortFns: { alphanumeric: sortFn_alphanumeric, basic: sortFn_basic },
  filterFns: { includesString: filterFn_includesString },
});

function toCsv<T>(rows: T[], columns: DataTableColumn<T>[]) {
  const cols = columns.filter((c) => c.csv !== false);
  const escape = (v: unknown) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [cols.map((c) => escape(c.header)).join(","), ...rows.map((r) => cols.map((c) => escape(c.value(r))).join(","))].join("\r\n");
}

function download(filename: string, content: string) {
  // UTF-8 BOM so Excel opens Thai text correctly.
  const blob = new Blob(["﻿", content], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/**
 * Sortable, searchable, paginated table with density toggle and client-side CSV export (exports the
 * filtered + sorted rows, all pages). Pass `loading` / `error` to render states in place.
 */
export function DataTable<T extends RowData>({
  data,
  columns,
  caption,
  getRowId,
  pageSize = 25,
  initialSort,
  exportName,
  toolbar,
  loading,
  error,
  onRetry,
  onRowClick,
  className,
}: {
  data: T[] | undefined;
  columns: DataTableColumn<T>[];
  /** Accessible table caption (visually hidden). */
  caption: string;
  getRowId?: (row: T, index: number) => string;
  pageSize?: number;
  initialSort?: SortingState;
  /** File name stem for CSV export; omit to hide the export button. */
  exportName?: string;
  toolbar?: ReactNode;
  loading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  onRowClick?: (row: T) => void;
  className?: string;
}) {
  const t = useT(common);
  const [density, setDensity] = useState<"compact" | "comfortable">("comfortable");
  const [sorting, setSorting] = useState<SortingState>(initialSort ?? []);
  const [globalFilter, setGlobalFilter] = useState("");
  const [pagination, setPagination] = useState({ pageIndex: 0, pageSize });

  const rows = useMemo(() => data ?? [], [data]);
  const tableColumns = useMemo<ColumnDef<typeof features, T, unknown>[]>(
    () =>
      columns.map((c) => ({
        id: c.id,
        header: c.header,
        accessorFn: (row: T) => c.value(row) ?? null,
        enableSorting: c.sortable !== false,
        enableGlobalFilter: c.searchable !== false,
        sortFn: "alphanumeric",
        sortUndefined: "last",
      })) as ColumnDef<typeof features, T, unknown>[],
    [columns],
  );

  const table = useTable({
    features,
    columns: tableColumns,
    data: rows,
    getRowId,
    state: { sorting, globalFilter, pagination },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    onPaginationChange: setPagination,
    globalFilterFn: "includesString",
    getColumnCanGlobalFilter: () => true,
  });

  const filteredCount = table.getFilteredRowModel().rows.length;
  const pageCount = Math.max(1, table.getPageCount());
  const colById = new Map(columns.map((c) => [c.id, c]));
  const pad = density === "compact" ? "px-3 py-1" : "px-3 py-2.5";

  const exportCsv = () => {
    const sorted = table.getSortedRowModel().rows.map((r) => r.original);
    download(`${exportName ?? "table"}.csv`, toCsv(sorted, columns));
  };

  return (
    <div className={cn("flex min-w-0 flex-col gap-3", className)}>
      <div className="flex flex-wrap items-center gap-2" data-print-hide>
        <label className="relative min-w-40 flex-1 sm:max-w-72">
          <span className="sr-only">{t.table.search}</span>
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-subtle-foreground" aria-hidden />
          <Input
            value={globalFilter}
            onChange={(e) => {
              setGlobalFilter(e.target.value);
              setPagination((p) => ({ ...p, pageIndex: 0 }));
            }}
            placeholder={t.table.searchPlaceholder}
            className="h-8 pl-8 text-[0.8125rem]"
            type="search"
          />
        </label>
        {toolbar}
        <div className="ml-auto flex items-center gap-2">
          <span className="tabular text-xs text-muted-foreground" aria-live="polite">
            {t.table.rows(filteredCount)}
          </span>
          <ToggleGroup
            type="single"
            value={density}
            onValueChange={(v) => v && setDensity(v as typeof density)}
            aria-label={t.table.density}
          >
            <ToggleGroupItem value="comfortable" aria-label={t.table.comfortable}>
              <Rows3 aria-hidden />
            </ToggleGroupItem>
            <ToggleGroupItem value="compact" aria-label={t.table.compact}>
              <Rows4 aria-hidden />
            </ToggleGroupItem>
          </ToggleGroup>
          {exportName ? (
            <Button variant="outline" size="sm" onClick={exportCsv} disabled={!filteredCount}>
              <Download aria-hidden />
              <span className="max-sm:sr-only">{t.table.exportCsv}</span>
            </Button>
          ) : null}
        </div>
      </div>

      {error ? (
        <ErrorState error={error} onRetry={onRetry} compact />
      ) : (
        <div tabIndex={0} role="region" aria-label={caption} className="relative overflow-x-auto rounded-lg border border-border bg-surface focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none">
          <table className="tabular w-full border-collapse text-left text-[0.8125rem]">
            <caption className="sr-only">{caption}</caption>
            <thead className="bg-surface-2">
              {table.getHeaderGroups().map((group) => (
                <tr key={group.id}>
                  {group.headers.map((header) => {
                    const col = colById.get(header.column.id);
                    const sorted = header.column.getIsSorted();
                    const canSort = header.column.getCanSort();
                    const align = col?.align ?? "left";
                    return (
                      <th
                        key={header.id}
                        scope="col"
                        aria-sort={sorted === "asc" ? "ascending" : sorted === "desc" ? "descending" : canSort ? "none" : undefined}
                        className={cn("border-b border-border text-xs font-semibold whitespace-nowrap text-muted-foreground", pad, align === "right" && "text-right", align === "center" && "text-center")}
                      >
                        {canSort ? (
                          <button
                            type="button"
                            onClick={header.column.getToggleSortingHandler()}
                            className={cn("inline-flex items-center gap-1 rounded hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none", align === "right" && "flex-row-reverse")}
                          >
                            {col?.header}
                            {sorted === "asc" ? <ArrowUp className="size-3" aria-hidden /> : sorted === "desc" ? <ArrowDown className="size-3" aria-hidden /> : <ArrowUpDown className="size-3 opacity-40" aria-hidden />}
                            <span className="sr-only">
                              {sorted === "asc" ? t.table.sortAsc : sorted === "desc" ? t.table.sortDesc : t.table.sortNone}
                            </span>
                          </button>
                        ) : (
                          col?.header
                        )}
                      </th>
                    );
                  })}
                </tr>
              ))}
            </thead>
            <tbody>
              {loading
                ? Array.from({ length: 5 }, (_, i) => (
                    <tr key={i} className="border-b border-border last:border-0">
                      {columns.map((c) => (
                        <td key={c.id} className={pad}>
                          <Skeleton className="h-4 w-full" />
                        </td>
                      ))}
                    </tr>
                  ))
                : table.getRowModel().rows.map((row) => (
                    <tr
                      key={row.id}
                      onClick={onRowClick ? () => onRowClick(row.original) : undefined}
                      className={cn("border-b border-border transition-colors last:border-0 hover:bg-surface-2/70", onRowClick && "cursor-pointer")}
                    >
                      {columns.map((c) => (
                        <td key={c.id} className={cn(pad, c.align === "right" && "text-right", c.align === "center" && "text-center", c.className)}>
                          {c.cell ? c.cell(row.original) : (c.value(row.original) ?? "—")}
                        </td>
                      ))}
                    </tr>
                  ))}
            </tbody>
          </table>
          {!loading && rows.length === 0 ? <EmptyState compact className="rounded-none border-0" /> : null}
          {!loading && rows.length > 0 && filteredCount === 0 ? <EmptyState compact title={t.table.noResults} body=" " className="rounded-none border-0" /> : null}
        </div>
      )}

      {!loading && !error && pageCount > 1 ? (
        <nav className="flex items-center justify-end gap-2 text-xs text-muted-foreground" aria-label={t.table.page(pagination.pageIndex + 1, pageCount)}>
          <span className="tabular">{t.table.page(pagination.pageIndex + 1, pageCount)}</span>
          <Button variant="outline" size="icon-sm" onClick={() => table.previousPage()} disabled={!table.getCanPreviousPage()} aria-label={t.table.previous}>
            <ChevronLeft aria-hidden />
          </Button>
          <Button variant="outline" size="icon-sm" onClick={() => table.nextPage()} disabled={!table.getCanNextPage()} aria-label={t.table.next}>
            <ChevronRight aria-hidden />
          </Button>
        </nav>
      ) : null}
    </div>
  );
}
