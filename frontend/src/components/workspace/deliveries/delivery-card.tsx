"use client";

import {
  ArrowUpRightIcon,
  CheckCircle2Icon,
  Clock3Icon,
  DownloadIcon,
  EyeIcon,
  FileCode2Icon,
  FileIcon,
  FileImageIcon,
  FileSpreadsheetIcon,
  FileTextIcon,
  PauseCircleIcon,
  PresentationIcon,
  XCircleIcon,
} from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter } from "@/components/ui/card";
import { urlOfArtifact } from "@/core/artifacts/utils";
import { type Delivery } from "@/core/deliveries/api";
import { deliveryFileType } from "@/core/deliveries/file-type";
import { useI18n } from "@/core/i18n/hooks";
import { pathOfThread } from "@/core/threads/utils";

const fileIcons = {
  document: FileTextIcon,
  spreadsheet: FileSpreadsheetIcon,
  presentation: PresentationIcon,
  image: FileImageIcon,
  code: FileCode2Icon,
  other: FileIcon,
};

export function DeliveryCard({
  delivery,
  onPreview,
}: {
  delivery: Delivery;
  onPreview: (filepath: string) => void;
}) {
  const { locale, t } = useI18n();
  const sourceHref = pathOfThread({
    thread_id: delivery.thread_id,
    context: { agent_name: delivery.agent_name ?? undefined },
  });
  const status =
    delivery.status === "success"
      ? {
          Icon: CheckCircle2Icon,
          label: t.deliveries.statusSuccess,
          variant: "secondary" as const,
        }
      : delivery.status === "error"
        ? {
            Icon: XCircleIcon,
            label: t.deliveries.statusError,
            variant: "destructive" as const,
          }
        : delivery.status === "interrupted"
          ? {
              Icon: PauseCircleIcon,
              label: t.deliveries.statusInterrupted,
              variant: "outline" as const,
            }
          : {
              Icon: Clock3Icon,
              label: t.deliveries.statusTimeout,
              variant: "outline" as const,
            };
  return (
    <article className="min-w-0 space-y-4 rounded-2xl border p-4 sm:p-5">
      <div className="flex min-w-0 flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1 space-y-1">
          <Link
            className="block truncate font-medium underline-offset-4 hover:underline"
            href={sourceHref}
          >
            {delivery.thread_title ?? t.deliveries.untitledChat}
          </Link>
          <p className="text-muted-foreground text-xs">
            {new Date(delivery.created_at).toLocaleString(locale)}
          </p>
        </div>
        <Badge variant={status.variant}>
          <status.Icon aria-hidden="true" />
          {status.label}
        </Badge>
      </div>
      <div className="grid min-w-0 gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {delivery.paths.map((path) => {
          const category = deliveryFileType(path);
          const Icon = fileIcons[category];
          return (
            <Card key={path} className="min-w-0 gap-4 py-4 shadow-none">
              <CardContent className="flex min-w-0 items-center gap-3 px-4">
                <div className="bg-muted text-muted-foreground flex size-10 shrink-0 items-center justify-center rounded-lg">
                  <Icon className="size-5" aria-hidden="true" />
                </div>
                <div className="min-w-0 space-y-1">
                  <p className="truncate text-sm font-medium" title={path}>
                    {path.split("/").at(-1)}
                  </p>
                  <p className="text-muted-foreground text-xs">
                    {t.deliveries.fileTypes[category]}
                  </p>
                </div>
              </CardContent>
              <CardFooter className="flex-wrap gap-2 px-4">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => onPreview(path)}
                >
                  <EyeIcon aria-hidden="true" />
                  {t.deliveries.open}
                </Button>
                <Button variant="outline" size="sm" asChild>
                  <a
                    href={urlOfArtifact({
                      threadId: delivery.thread_id,
                      filepath: path,
                      download: true,
                    })}
                  >
                    <DownloadIcon aria-hidden="true" />
                    {t.common.download}
                  </a>
                </Button>
              </CardFooter>
            </Card>
          );
        })}
      </div>
      {delivery.files_truncated && (
        <p className="text-muted-foreground text-xs">
          {t.deliveries.filesTruncated}
        </p>
      )}
      <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
        <Link
          className="inline-flex items-center gap-1 text-sm underline-offset-4 hover:underline"
          href={sourceHref}
        >
          {t.deliveries.sourceChat}
          <ArrowUpRightIcon className="size-3.5" aria-hidden="true" />
        </Link>
        <p
          className="text-muted-foreground min-w-0 truncate text-xs"
          title={delivery.run_id}
        >
          {t.deliveries.runLabel} {delivery.run_id}
        </p>
      </div>
    </article>
  );
}
