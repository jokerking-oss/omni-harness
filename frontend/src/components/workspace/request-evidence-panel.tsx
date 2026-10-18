"use client";

import { useInfiniteQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/core/auth/AuthProvider";
import { useI18n } from "@/core/i18n/hooks";
import { fetchRequestEvidence } from "@/core/messages/request-evidence";

export function RequestEvidencePanel({
  threadId,
  runId,
}: {
  threadId: string;
  runId: string;
}) {
  const { t } = useI18n();
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const query = useInfiniteQuery({
    queryKey: ["request-evidence", user?.id, threadId, runId],
    initialPageParam: undefined as number | undefined,
    queryFn: ({ signal, pageParam }) =>
      fetchRequestEvidence(threadId, runId, signal, pageParam),
    getNextPageParam: (page) => page.nextAfterSeq,
    enabled: open,
  });
  return (
    <details
      className="border-border/60 mt-2 rounded-md border p-3 text-xs"
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary className="cursor-pointer font-medium">
        {t.requestEvidence.title}
      </summary>
      {open && (
        <div className="mt-3 space-y-3">
          <p className="text-muted-foreground">
            {t.requestEvidence.description}
          </p>
          {query.isLoading && <p role="status">{t.common.loading}</p>}
          {query.isError && (
            <div role="alert">
              {t.requestEvidence.loadFailed}{" "}
              <Button
                variant="outline"
                size="sm"
                onClick={() => void query.refetch()}
              >
                {t.requestEvidence.retry}
              </Button>
            </div>
          )}
          {query.data &&
            query.data.pages.every((page) => page.events.length === 0) && (
              <p>{t.requestEvidence.empty}</p>
            )}
          {query.data?.pages
            .flatMap((page) => page.events)
            .map((event) => (
              <div
                key={event.seq}
                className="bg-muted/30 space-y-1 rounded p-2"
              >
                <div className="font-medium">
                  #{event.metadata.llm_call_index} · {event.metadata.caller}
                </div>
                <div>
                  {event.content.boundary === "provider_payload"
                    ? t.requestEvidence.providerPayload
                    : t.requestEvidence.modelInput}
                </div>
                <div>
                  {t.requestEvidence.messages}: {event.content.message_count} ·{" "}
                  {t.requestEvidence.tools}: {event.content.tool_count} ·{" "}
                  {event.content.bytes.toLocaleString()} B
                </div>
                <div>
                  {t.requestEvidence.added}: {event.content.delta.added} ·{" "}
                  {t.requestEvidence.removed}: {event.content.delta.removed} ·{" "}
                  {t.requestEvidence.reused}: {event.content.delta.reused} · Δ{" "}
                  {event.content.delta.bytes.toLocaleString()} B
                </div>
                {event.content.truncated && (
                  <p>{t.requestEvidence.truncated}</p>
                )}
                <code className="block text-[10px] break-all">
                  SHA-256 {event.content.sha256}
                </code>
                <details>
                  <summary>{t.requestEvidence.components}</summary>
                  <ul className="space-y-1 pt-2">
                    {event.content.components.map((component, index) => (
                      <li key={index}>
                        {component.kind} · {component.bytes} B ·{" "}
                        <code>{component.sha256.slice(0, 12)}</code>
                      </li>
                    ))}
                    {event.content.tools.map((tool, index) => (
                      <li key={`tool-${index}`}>
                        {tool.name} · {tool.bytes} B ·{" "}
                        <code>{tool.sha256.slice(0, 12)}</code>
                      </li>
                    ))}
                  </ul>
                </details>
              </div>
            ))}
          {query.hasNextPage && (
            <Button
              variant="outline"
              size="sm"
              disabled={query.isFetchingNextPage}
              onClick={() => void query.fetchNextPage()}
            >
              {t.requestEvidence.loadMore}
            </Button>
          )}
        </div>
      )}
    </details>
  );
}
