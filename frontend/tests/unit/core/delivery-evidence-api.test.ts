import { beforeEach, expect, it, rs } from "@rstest/core";

rs.mock("@/core/api/fetcher", () => ({ fetch: rs.fn() }));
rs.mock("@/core/config", () => ({ getBackendBaseURL: () => "" }));
import { fetch } from "@/core/api/fetcher";
import { fetchDeliveries } from "@/core/deliveries/api";
import { fetchRequestEvidence } from "@/core/messages/request-evidence";

const mockedFetch = rs.mocked(fetch);
beforeEach(() => {
  mockedFetch.mockReset();
});

it("paginates deliveries and forwards cancellation", async () => {
  mockedFetch.mockResolvedValue(
    new Response(
      JSON.stringify({
        data: [],
        has_more: false,
        scope: "history",
        scanned_runs: 0,
      }),
    ),
  );
  const signal = new AbortController().signal;
  await fetchDeliveries(
    { before_created_at: "2026-10-11T00:00:00+00:00", before_run_id: "r/1" },
    signal,
  );
  expect(mockedFetch.mock.calls[0]?.[0]).toContain("before_run_id=r%2F1");
  expect(mockedFetch.mock.calls[0]?.[1]?.signal).toBe(signal);
});

it("loads request evidence through encoded thread and run IDs", async () => {
  mockedFetch.mockResolvedValue(new Response("[]"));
  await expect(fetchRequestEvidence("t / 1", "r/1")).resolves.toEqual({
    events: [],
    nextAfterSeq: undefined,
  });
  expect(mockedFetch.mock.calls[0]?.[0]).toContain(
    "threads/t%20%2F%201/runs/r%2F1/events",
  );
});

it("surfaces failed requests for retry", async () => {
  mockedFetch.mockResolvedValue(new Response("unavailable", { status: 503 }));
  await expect(fetchDeliveries(null)).rejects.toThrow("503");
  await expect(fetchRequestEvidence("t", "r")).rejects.toThrow("503");
});

it("advances past truncated legacy records without rendering invalid evidence", async () => {
  mockedFetch.mockResolvedValue(
    new Response(
      JSON.stringify(
        Array.from({ length: 50 }, (_, index) => ({
          seq: index + 1,
          content: "truncated json",
        })),
      ),
    ),
  );
  await expect(fetchRequestEvidence("t", "r")).resolves.toEqual({
    events: [],
    nextAfterSeq: 50,
  });
});
