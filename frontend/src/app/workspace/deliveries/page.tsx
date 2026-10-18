"use client";

import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import { FolderOpenIcon, RefreshCwIcon, SearchIcon } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ArtifactViewer } from "@/components/workspace/artifacts/artifact-viewer";
import { DeliveryCard } from "@/components/workspace/deliveries/delivery-card";
import {
  WorkspaceBody,
  WorkspaceContainer,
  WorkspaceHeader,
} from "@/components/workspace/workspace-container";
import { useAuth } from "@/core/auth/AuthProvider";
import {
  fetchDeliveries,
  type DeliveryCursor,
  type DeliveryFileType,
  type DeliveryFilters,
} from "@/core/deliveries/api";
import { useI18n } from "@/core/i18n/hooks";

const fileTypes: DeliveryFileType[] = [
  "all",
  "document",
  "spreadsheet",
  "presentation",
  "image",
  "code",
  "other",
];

function deliveryQueryKey(
  userId: string | undefined,
  filters: DeliveryFilters,
) {
  return ["deliveries", userId, filters.q, filters.file_type];
}

export default function DeliveriesPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<DeliveryFilters>({
    q: "",
    file_type: "all",
  });
  const [selected, setSelected] = useState<{
    threadId: string;
    filepath: string;
  } | null>(null);
  const query = useInfiniteQuery({
    queryKey: deliveryQueryKey(user?.id, filters),
    initialPageParam: null as DeliveryCursor | null,
    queryFn: ({ pageParam, signal }) =>
      fetchDeliveries(pageParam, signal, filters),
    getNextPageParam: (page) =>
      page.has_more && page.next_before_created_at && page.next_before_run_id
        ? {
            before_created_at: page.next_before_created_at,
            before_run_id: page.next_before_run_id,
          }
        : undefined,
  });
  const rows = [
    ...new Map(
      query.data?.pages
        .flatMap((page) => page.data)
        .map((row) => [row.run_id, row]),
    ).values(),
  ];
  const loadedFiles = rows.reduce((count, row) => count + row.paths.length, 0);
  const searchTooLong = [...search.trim()].length > 200;
  const hasFilters = filters.q !== "" || filters.file_type !== "all";
  function applyFilters(next: DeliveryFilters) {
    if (next.q === filters.q && next.file_type === filters.file_type) return;
    // Revisiting a cached filter must still begin at its first scan window.
    queryClient.removeQueries({
      queryKey: deliveryQueryKey(user?.id, next),
      exact: true,
    });
    setFilters(next);
  }
  return (
    <WorkspaceContainer>
      <WorkspaceHeader />
      <WorkspaceBody>
        <div className="w-full max-w-6xl min-w-0 space-y-6 overflow-auto p-4 md:p-8">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="bg-muted/50 mb-3 flex size-11 items-center justify-center rounded-xl border">
                <FolderOpenIcon className="size-5" aria-hidden="true" />
              </div>
              <h1 className="text-2xl font-semibold">{t.deliveries.title}</h1>
              <p className="text-muted-foreground mt-2 text-sm">
                {t.deliveries.description}
              </p>
            </div>
            <Button
              variant="outline"
              disabled={query.isFetching}
              onClick={() => void query.refetch()}
            >
              <RefreshCwIcon aria-hidden="true" />
              {t.deliveries.refresh}
            </Button>
          </div>
          <form
            className="flex flex-wrap items-start gap-3 rounded-xl border p-3"
            onSubmit={(event) => {
              event.preventDefault();
              if (!searchTooLong)
                applyFilters({ ...filters, q: search.trim() });
            }}
          >
            <div className="min-w-0 basis-full space-y-1 sm:flex-1 sm:basis-auto">
              <Input
                aria-label={t.deliveries.searchLabel}
                aria-invalid={searchTooLong}
                aria-describedby={
                  searchTooLong ? "delivery-search-error" : undefined
                }
                placeholder={t.deliveries.searchPlaceholder}
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
              {searchTooLong && (
                <p
                  id="delivery-search-error"
                  className="text-destructive text-xs"
                >
                  {t.deliveries.searchTooLong}
                </p>
              )}
            </div>
            <Select
              value={filters.file_type}
              onValueChange={(value) =>
                applyFilters({
                  ...filters,
                  file_type: value as DeliveryFileType,
                })
              }
            >
              <SelectTrigger
                aria-label={t.deliveries.fileTypeLabel}
                className="w-[180px] max-w-full"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {fileTypes.map((fileType) => (
                  <SelectItem key={fileType} value={fileType}>
                    {t.deliveries.fileTypes[fileType]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button type="submit" disabled={searchTooLong}>
              <SearchIcon aria-hidden="true" />
              {t.deliveries.search}
            </Button>
            {(hasFilters || search !== "") && (
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  setSearch("");
                  applyFilters({ q: "", file_type: "all" });
                }}
              >
                {t.deliveries.clearFilters}
              </Button>
            )}
          </form>
          <div className="bg-muted/40 space-y-2 rounded-xl p-4">
            <p className="text-sm">{t.deliveries.currentFilesNotice}</p>
            {query.data?.pages[0]?.scope === "recent_runs" && (
              <p className="text-muted-foreground text-xs">
                {t.deliveries.recentRunsNotice}
              </p>
            )}
          </div>
          {query.isSuccess && (
            <p
              role="status"
              className="text-muted-foreground flex flex-wrap items-center gap-2 text-sm"
            >
              <Badge variant="secondary">
                {t.deliveries.loadedFiles(loadedFiles)}
              </Badge>
              {t.deliveries.loadedRuns(rows.length)}
            </p>
          )}
          {query.isLoading && <p role="status">{t.common.loading}</p>}
          {query.isError && (
            <div role="alert" className="space-x-3">
              {t.deliveries.loadFailed}
              <Button variant="outline" onClick={() => void query.refetch()}>
                {t.deliveries.retry}
              </Button>
            </div>
          )}
          {query.isSuccess && rows.length === 0 && (
            <div className="rounded-xl border border-dashed p-10 text-center">
              <FolderOpenIcon
                className="text-muted-foreground mx-auto mb-3 size-8"
                aria-hidden="true"
              />
              <h2 className="font-medium">
                {query.hasNextPage
                  ? t.deliveries.scanEmptyTitle
                  : t.deliveries.emptyTitle}
              </h2>
              <p className="text-muted-foreground mt-2 text-sm">
                {query.hasNextPage
                  ? t.deliveries.scanEmptyDescription
                  : hasFilters
                    ? t.deliveries.filteredEmptyDescription
                    : t.deliveries.emptyDescription}
              </p>
            </div>
          )}
          {rows.map((row) => (
            <DeliveryCard
              key={row.run_id}
              delivery={row}
              onPreview={(filepath) =>
                setSelected({ threadId: row.thread_id, filepath })
              }
            />
          ))}
          {query.hasNextPage && (
            <Button
              variant="outline"
              disabled={query.isFetchingNextPage}
              onClick={() => void query.fetchNextPage()}
            >
              {query.isFetchingNextPage
                ? t.common.loading
                : t.deliveries.loadMore}
            </Button>
          )}
        </div>
        <Dialog
          open={selected !== null}
          onOpenChange={(open) => {
            if (!open) setSelected(null);
          }}
        >
          <DialogContent className="h-[85vh] max-w-5xl overflow-hidden p-0 sm:max-w-5xl">
            <DialogTitle className="sr-only">{selected?.filepath}</DialogTitle>
            <DialogDescription className="sr-only">
              {t.deliveries.currentFilesNotice}
            </DialogDescription>
            {selected && (
              <div className="h-full min-h-0 [&>div]:h-full">
                <ArtifactViewer
                  key={`${selected.threadId}:${selected.filepath}`}
                  {...selected}
                />
              </div>
            )}
          </DialogContent>
        </Dialog>
      </WorkspaceBody>
    </WorkspaceContainer>
  );
}
