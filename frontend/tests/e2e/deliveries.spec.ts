import { expect, test } from "@playwright/test";

import { mockLangGraphAPI } from "./utils/mock-api";

test.beforeEach(({ page }) => {
  mockLangGraphAPI(page);
});

test("delivery receipts paginate, preview and link to their source", async ({
  page,
}) => {
  await page.route("**/api/deliveries/page?*", (route) => {
    const next = new URL(route.request().url()).searchParams.has(
      "before_run_id",
    );
    return route.fulfill({
      json: {
        data: [
          {
            run_id: next ? "old" : "new",
            thread_id: "source-thread",
            thread_title: next ? "Older delivery" : "Research delivery",
            agent_name: "researcher",
            status: "success",
            created_at: "2026-10-11T00:00:00Z",
            paths: ["/mnt/user-data/outputs/report.md"],
            files_truncated: false,
          },
        ],
        scope: "recent_runs",
        scanned_runs: 1,
        has_more: !next,
        next_before_created_at: "2026-10-11T00:00:00Z",
        next_before_run_id: "new",
      },
    });
  });
  await page.route("**/artifacts/mnt/user-data/outputs/report.md*", (route) =>
    route.fulfill({
      body: "# Delivered report\n\nVerified preview content.",
      contentType: "text/markdown",
      headers: { "Accept-Ranges": "bytes", ETag: '"test-revision"' },
    }),
  );
  await page.goto("/workspace/deliveries");
  await expect(
    page.getByRole("heading", { name: "Deliveries", exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/not complete history/)).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Open source chat" }),
  ).toHaveAttribute("href", "/workspace/agents/researcher/chats/source-thread");
  await page.getByRole("button", { name: "Preview", exact: true }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByText("Verified preview content.")).toBeVisible();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Load more" }).click();
  await expect(
    page.getByRole("link", { name: "Older delivery" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Load more" })).toHaveCount(0);
});

test("delivery empty state and retry are visible", async ({ page }) => {
  let failed = true;
  await page.route("**/api/deliveries/page?*", (route) =>
    failed
      ? route.fulfill({ status: 503, json: { detail: "Unavailable" } })
      : route.fulfill({
          json: {
            data: [],
            scope: "history",
            scanned_runs: 0,
            has_more: false,
          },
        }),
  );
  await page.goto("/workspace/deliveries");
  await expect(
    page.getByRole("alert").filter({ hasText: "Could not load deliveries" }),
  ).toBeVisible({ timeout: 15000 });
  failed = false;
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "No deliveries found" }),
  ).toBeVisible();
});

test("delivery search and file types start fresh pages and can be cleared", async ({
  page,
}) => {
  const requests: URLSearchParams[] = [];
  await page.route("**/api/deliveries/page?*", (route) => {
    const params = new URL(route.request().url()).searchParams;
    requests.push(params);
    const filtered = params.get("q") === "预算";
    const next = params.has("before_run_id");
    return route.fulfill({
      json: {
        data: [
          {
            run_id: `${filtered ? "filtered" : "initial"}-${next ? "old" : "new"}`,
            thread_id: "source-thread",
            thread_title: filtered ? "Budget delivery" : "Research delivery",
            agent_name: null,
            status: "success",
            created_at: "2026-10-11T00:00:00Z",
            paths: filtered
              ? ["/mnt/user-data/outputs/预算.xlsx"]
              : [
                  "/mnt/user-data/outputs/report.md",
                  "/mnt/user-data/outputs/revenue.csv",
                  "/mnt/user-data/outputs/presentation.pptx",
                  "/mnt/user-data/outputs/chart.png",
                  "/mnt/user-data/outputs/dashboard.html",
                  "/mnt/user-data/outputs/assets.zip",
                ],
            files_truncated: false,
          },
        ],
        scope: "history",
        scanned_runs: 1,
        has_more: !next,
        next_before_created_at: "2026-10-11T00:00:00Z",
        next_before_run_id: "cursor-new",
      },
    });
  });
  await page.goto("/workspace/deliveries");
  await expect(page.getByText("report.md", { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 1440, height: 1100 });
  await page.screenshot({
    path: ".next/workbarley-deliveries-desktop.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Load more", exact: true }).click();
  await expect(page.getByRole("button", { name: "Load more" })).toHaveCount(0);
  await page.getByRole("textbox", { name: "Search deliveries" }).fill("预算");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByText("预算.xlsx", { exact: true })).toBeVisible();
  await expect(page.getByText("report.md", { exact: true })).toHaveCount(0);
  const searched = requests.find((params) => params.get("q") === "预算");
  expect(searched?.has("before_run_id")).toBe(false);
  await page.getByRole("combobox", { name: "File type" }).click();
  await page.getByRole("option", { name: "Spreadsheets", exact: true }).click();
  await expect
    .poll(() =>
      requests.some((params) => params.get("file_type") === "spreadsheet"),
    )
    .toBe(true);
  const typed = requests.find(
    (params) => params.get("file_type") === "spreadsheet",
  );
  expect(typed?.get("q")).toBe("预算");
  expect(typed?.has("before_run_id")).toBe(false);
  await page.getByRole("button", { name: "Load more", exact: true }).click();
  await expect
    .poll(() =>
      requests.some(
        (params) =>
          params.get("file_type") === "spreadsheet" &&
          params.get("q") === "预算" &&
          params.get("before_run_id") === "cursor-new",
      ),
    )
    .toBe(true);
  await page
    .getByRole("button", { name: "Clear filters", exact: true })
    .click();
  await expect(
    page.getByRole("textbox", { name: "Search deliveries" }),
  ).toHaveValue("");
  await expect(page.getByText("预算.xlsx", { exact: true })).toHaveCount(0);
  await expect(
    page.getByText("report.md", { exact: true }).first(),
  ).toBeVisible();
});

test("an empty delivery scan can continue to an older matching file", async ({
  page,
}) => {
  await page.route("**/api/deliveries/page?*", (route) => {
    const next = new URL(route.request().url()).searchParams.has(
      "before_run_id",
    );
    return route.fulfill({
      json: {
        data: next
          ? [
              {
                run_id: "older-match",
                thread_id: "source-thread",
                thread_title: "Older delivery",
                agent_name: null,
                status: "success",
                created_at: "2026-10-10T00:00:00Z",
                paths: ["/mnt/user-data/outputs/older.pdf"],
                files_truncated: false,
              },
            ]
          : [],
        scope: "history",
        scanned_runs: next ? 1 : 50,
        has_more: !next,
        next_before_created_at: next ? null : "2026-10-11T00:00:00Z",
        next_before_run_id: next ? null : "scan-cursor",
      },
    });
  });
  await page.goto("/workspace/deliveries");
  await expect(
    page.getByRole("button", { name: "Load more", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "No deliveries found" }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Load more", exact: true }).click();
  await expect(page.getByText("older.pdf", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Load more" })).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: ".next/workbarley-deliveries-mobile.png",
    fullPage: true,
  });
});
