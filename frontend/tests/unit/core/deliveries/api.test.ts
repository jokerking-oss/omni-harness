import { beforeEach, describe, expect, it, rs } from "@rstest/core";

rs.mock("@/core/api/fetcher", () => ({ fetch: rs.fn() }));
rs.mock("@/core/config", () => ({ getBackendBaseURL: () => "" }));

import { fetch } from "@/core/api/fetcher";
import { fetchDeliveries } from "@/core/deliveries/api";

const mockedFetch = rs.mocked(fetch);

beforeEach(() => {
  mockedFetch.mockReset();
  mockedFetch.mockImplementation(() =>
    Promise.resolve(
      new Response(JSON.stringify({ data: [], has_more: false })),
    ),
  );
});

describe("delivery filters", () => {
  it("encodes submitted Unicode search and category on every cursor page", async () => {
    const signal = new AbortController().signal;
    await fetchDeliveries(
      { before_created_at: "2026-10-11T00:00:00+00:00", before_run_id: "r/1" },
      signal,
      { q: "  预算 & report  ", file_type: "spreadsheet" },
    );
    const params = new URL(
      mockedFetch.mock.calls[0]![0] as string,
      "http://localhost",
    ).searchParams;
    expect(params.get("q")).toBe("预算 & report");
    expect(params.get("file_type")).toBe("spreadsheet");
    expect(params.get("before_run_id")).toBe("r/1");
    expect(params.get("limit")).toBe("20");
    expect(mockedFetch.mock.calls[0]?.[1]?.signal).toBe(signal);
  });

  it("keeps the legacy call and blank all-file filters unfiltered", async () => {
    await fetchDeliveries(null);
    await fetchDeliveries(null, undefined, { q: "  ", file_type: "all" });
    for (const [url] of mockedFetch.mock.calls) {
      const params = new URL(url as string, "http://localhost").searchParams;
      expect(params.has("q")).toBe(false);
      expect(params.has("file_type")).toBe(false);
      expect(params.has("before_run_id")).toBe(false);
    }
  });

  it("surfaces filter validation failures", async () => {
    mockedFetch.mockResolvedValue(
      new Response("invalid filter", { status: 422 }),
    );
    await expect(
      fetchDeliveries(null, undefined, {
        q: "x".repeat(201),
        file_type: "all",
      }),
    ).rejects.toThrow("HTTP 422");
  });
});
