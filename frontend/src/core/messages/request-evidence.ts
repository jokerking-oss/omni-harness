import { z } from "zod";

import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";

const hash = z.string().regex(/^[a-f0-9]{64}$/);
const count = z.number().int().nonnegative();
const fingerprint = z.object({ sha256: hash, bytes: count });
const evidenceSchema = z.object({
  seq: z.number().int().positive(),
  metadata: z
    .object({ caller: z.string().optional(), llm_call_index: count.optional() })
    .default({}),
  content: z.object({
    version: z.literal(1),
    boundary: z.enum(["provider_payload", "model_input"]),
    sha256: hash,
    bytes: count,
    message_count: count,
    tool_count: count,
    truncated: z.boolean(),
    delta: z.object({
      added: count,
      removed: count,
      reused: count,
      bytes: z.number().int(),
    }),
    tools: z.array(fingerprint.extend({ name: z.string() })).max(8),
    components: z
      .array(fingerprint.extend({ kind: z.string(), index: count.optional() }))
      .max(18),
  }),
});
export type RequestEvidence = z.infer<typeof evidenceSchema>;
export type RequestEvidencePage = {
  events: RequestEvidence[];
  nextAfterSeq?: number;
};

export async function fetchRequestEvidence(
  threadId: string,
  runId: string,
  signal?: AbortSignal,
  afterSeq?: number,
): Promise<RequestEvidencePage> {
  const params = new URLSearchParams({
    event_types: "llm.request.evidence",
    limit: "50",
  });
  if (afterSeq !== undefined) params.set("after_seq", String(afterSeq));
  const response = await fetch(
    `${getBackendBaseURL()}/api/threads/${encodeURIComponent(threadId)}/runs/${encodeURIComponent(runId)}/events?${params}`,
    { signal },
  );
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const raw = (await response.json()) as unknown;
  if (!Array.isArray(raw)) throw new Error("Invalid request evidence page");
  const events = raw.flatMap((event: unknown) => {
    const parsed = evidenceSchema.safeParse(event);
    return parsed.success ? [parsed.data] : [];
  });
  const last = raw.at(-1) as { seq?: unknown } | undefined;
  const nextAfterSeq =
    raw.length === 50 &&
    typeof last?.seq === "number" &&
    Number.isSafeInteger(last.seq) &&
    last.seq > (afterSeq ?? 0)
      ? last.seq
      : undefined;
  return { events, nextAfterSeq };
}
