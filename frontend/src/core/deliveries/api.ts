import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";

export type DeliveryCursor = {
  before_created_at: string;
  before_run_id: string;
};
export type DeliveryFileType =
  | "all"
  | "document"
  | "spreadsheet"
  | "presentation"
  | "image"
  | "code"
  | "other";
export type DeliveryFilters = {
  q: string;
  file_type: DeliveryFileType;
};
export type Delivery = {
  run_id: string;
  thread_id: string;
  thread_title: string | null;
  agent_name: string | null;
  status: string;
  created_at: string;
  paths: string[];
  files_truncated: boolean;
};
export type DeliveryPage = {
  data: Delivery[];
  scope: "history" | "recent_runs";
  scanned_runs: number;
  has_more: boolean;
  next_before_created_at?: string | null;
  next_before_run_id?: string | null;
};

export async function fetchDeliveries(
  cursor: DeliveryCursor | null,
  signal?: AbortSignal,
  filters?: DeliveryFilters,
): Promise<DeliveryPage> {
  const params = new URLSearchParams({ limit: "20", ...cursor });
  const search = filters?.q.trim();
  if (search) params.set("q", search);
  if (filters?.file_type && filters.file_type !== "all") {
    params.set("file_type", filters.file_type);
  }
  const response = await fetch(
    `${getBackendBaseURL()}/api/deliveries/page?${params}`,
    { signal },
  );
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json() as Promise<DeliveryPage>;
}
