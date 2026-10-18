import { afterEach, beforeEach, describe, expect, it, rs } from "@rstest/core";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import {
  createContext,
  useContext,
  type ComponentProps,
  type PropsWithChildren,
} from "react";

rs.mock("next/link", () => ({
  default: ({ children, ...props }: ComponentProps<"a">) => (
    <a {...props}>{children}</a>
  ),
}));
rs.mock("@/core/auth/AuthProvider", () => ({
  useAuth: () => ({ user: { id: "owner-1" } }),
}));
rs.mock("@/core/config", () => ({ getBackendBaseURL: () => "" }));
rs.mock("@/core/deliveries/api", () => ({ fetchDeliveries: rs.fn() }));
rs.mock("@/components/workspace/artifacts/artifact-viewer", () => ({
  ArtifactViewer: ({ filepath }: { filepath: string }) => (
    <div>Preview: {filepath}</div>
  ),
}));
rs.mock("@/components/workspace/workspace-container", () => ({
  WorkspaceContainer: ({ children }: PropsWithChildren) => (
    <div>{children}</div>
  ),
  WorkspaceHeader: () => null,
  WorkspaceBody: ({ children }: PropsWithChildren) => <div>{children}</div>,
}));
// The real Radix select is covered by Playwright. Keep these tests focused on
// query cancellation and filter ownership using a native select interaction.
rs.mock("@/components/ui/select", () => {
  const Selection = createContext<{
    value: string;
    onValueChange: (value: string) => void;
  }>({
    value: "all",
    onValueChange: (_value: string) => undefined,
  });
  return {
    Select: ({
      children,
      value,
      onValueChange,
    }: PropsWithChildren<{
      value: string;
      onValueChange: (value: string) => void;
    }>) => (
      <Selection.Provider value={{ value, onValueChange }}>
        {children}
      </Selection.Provider>
    ),
    SelectTrigger: ({ children, ...props }: ComponentProps<"div">) => (
      <div {...props}>{children}</div>
    ),
    SelectValue: () => null,
    SelectContent: ({ children }: PropsWithChildren) => {
      const { value, onValueChange } = useContext(Selection);
      return (
        <select
          aria-label="File type"
          value={value}
          onChange={(event) => onValueChange(event.target.value)}
        >
          {children}
        </select>
      );
    },
    SelectItem: ({ children, value }: PropsWithChildren<{ value: string }>) => (
      <option value={value}>{children}</option>
    ),
  };
});

import DeliveriesPage from "@/app/workspace/deliveries/page";
import { fetchDeliveries, type DeliveryPage } from "@/core/deliveries/api";
import { I18nProvider } from "@/core/i18n/context";

const mockedFetch = rs.mocked(fetchDeliveries);
let queryClient: QueryClient;

function page(
  runId = "new",
  overrides: Partial<DeliveryPage> = {},
): DeliveryPage {
  return {
    data: [
      {
        run_id: runId,
        thread_id: "source-thread",
        thread_title: `Source ${runId}`,
        agent_name: "researcher",
        status: "success",
        created_at: "2026-10-11T00:00:00Z",
        paths: [`/mnt/user-data/outputs/${runId}.md`],
        files_truncated: false,
      },
    ],
    scope: "history",
    scanned_runs: 1,
    has_more: false,
    ...overrides,
  };
}

function Wrapper({ children }: PropsWithChildren) {
  return (
    <QueryClientProvider client={queryClient}>
      <I18nProvider initialLocale="en-US">{children}</I18nProvider>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  mockedFetch.mockReset();
});

afterEach(() => {
  cleanup();
  queryClient.clear();
});

describe("delivery workbench", () => {
  it("shows loaded counts only after success and preserves file actions", async () => {
    let resolveRead!: (value: DeliveryPage) => void;
    mockedFetch.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveRead = resolve;
        }),
    );
    render(<DeliveriesPage />, { wrapper: Wrapper });
    expect(screen.queryByText(/files? loaded/)).toBeNull();
    await act(async () => {
      resolveRead(page());
    });
    await waitFor(() =>
      expect(screen.getByText("1 file loaded")).toBeDefined(),
    );
    expect(screen.getByText("From 1 loaded run")).toBeDefined();
    expect(screen.getByText("Completed")).toBeDefined();
    expect(
      screen
        .getByRole("link", { name: "Open source chat" })
        .getAttribute("href"),
    ).toBe("/workspace/agents/researcher/chats/source-thread");
    expect(
      screen.getByRole("link", { name: "Download" }).getAttribute("href"),
    ).toContain("download=true");
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    expect(
      screen.getByText("Preview: /mnt/user-data/outputs/new.md"),
    ).toBeDefined();
  });

  it("cancels the obsolete read and starts submitted searches at page one", async () => {
    let resolveOld!: (value: DeliveryPage) => void;
    let oldSignal: AbortSignal | undefined;
    mockedFetch.mockImplementation((_cursor, signal, filters) => {
      if (!filters?.q) {
        oldSignal = signal;
        return new Promise((resolve) => {
          resolveOld = resolve;
        });
      }
      return Promise.resolve(page("filtered"));
    });
    render(<DeliveriesPage />, { wrapper: Wrapper });
    fireEvent.change(
      screen.getByRole("textbox", { name: "Search deliveries" }),
      { target: { value: "  预算  " } },
    );
    expect(mockedFetch).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    await waitFor(() => expect(screen.getByText("filtered.md")).toBeDefined());
    expect(oldSignal?.aborted).toBe(true);
    expect(mockedFetch.mock.calls[1]?.[0]).toBeNull();
    expect(mockedFetch.mock.calls[1]?.[2]).toEqual({
      q: "预算",
      file_type: "all",
    });
    await act(async () => {
      resolveOld(page("stale"));
    });
    expect(screen.queryByText("stale.md")).toBeNull();
  });

  it("resets cached filters to page one and sends selected types to the server", async () => {
    mockedFetch.mockImplementation((cursor, _signal, filters) =>
      Promise.resolve(
        filters?.file_type === "spreadsheet"
          ? page("server-match")
          : cursor
            ? page("older")
            : page("new", {
                has_more: true,
                next_before_created_at: "2026-10-11T00:00:00Z",
                next_before_run_id: "new",
              }),
      ),
    );
    render(<DeliveriesPage />, { wrapper: Wrapper });
    await waitFor(() => expect(screen.getByText("new.md")).toBeDefined());
    fireEvent.click(screen.getByRole("button", { name: "Load more" }));
    await waitFor(() => expect(screen.getByText("older.md")).toBeDefined());
    fireEvent.change(screen.getByRole("combobox", { name: "File type" }), {
      target: { value: "spreadsheet" },
    });
    // A server-authorized result is shown as returned, even if its filename
    // would not pass a duplicate local type filter.
    await waitFor(() =>
      expect(screen.getByText("server-match.md")).toBeDefined(),
    );
    expect(screen.queryByText("older.md")).toBeNull();
    expect(mockedFetch.mock.calls[2]?.[0]).toBeNull();
    expect(mockedFetch.mock.calls[2]?.[2]).toEqual({
      q: "",
      file_type: "spreadsheet",
    });
    fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    await waitFor(() => expect(screen.getByText("new.md")).toBeDefined());
    expect(screen.queryByText("older.md")).toBeNull();
    expect(mockedFetch.mock.calls[3]?.[0]).toBeNull();
  });

  it("continues scanning an empty window without announcing no results", async () => {
    mockedFetch.mockImplementation((cursor) =>
      Promise.resolve(
        cursor
          ? page("older-match")
          : page("", {
              data: [],
              has_more: true,
              scanned_runs: 50,
              next_before_created_at: "2026-10-11T00:00:00Z",
              next_before_run_id: "scan-end",
            }),
      ),
    );
    render(<DeliveriesPage />, { wrapper: Wrapper });
    await waitFor(() =>
      expect(screen.getByText("Keep looking in older runs")).toBeDefined(),
    );
    expect(
      screen.queryByRole("heading", { name: "No deliveries found" }),
    ).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Load more" }));
    await waitFor(() =>
      expect(screen.getByText("older-match.md")).toBeDefined(),
    );
    expect(mockedFetch.mock.calls[1]?.[0]?.before_run_id).toBe("scan-end");
  });

  it("hides counts on errors and retries the same query", async () => {
    mockedFetch
      .mockRejectedValueOnce(new Error("HTTP 503"))
      .mockResolvedValue(page("", { data: [] }));
    render(<DeliveriesPage />, { wrapper: Wrapper });
    await waitFor(() => expect(screen.getByRole("alert")).toBeDefined());
    expect(screen.queryByText(/files? loaded/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "No deliveries found" }),
      ).toBeDefined(),
    );
    expect(screen.getByText("0 files loaded")).toBeDefined();
  });

  it("counts Unicode search characters instead of UTF-16 code units", async () => {
    mockedFetch.mockResolvedValue(page());
    render(<DeliveriesPage />, { wrapper: Wrapper });
    await waitFor(() => expect(screen.getByText("new.md")).toBeDefined());
    const search = screen.getByRole("textbox", { name: "Search deliveries" });
    fireEvent.change(search, { target: { value: "😀".repeat(200) } });
    expect(search.getAttribute("aria-invalid")).toBe("false");
    fireEvent.change(search, { target: { value: "😀".repeat(201) } });
    expect(search.getAttribute("aria-invalid")).toBe("true");
    expect(
      screen.getByRole("button", { name: "Search" }).hasAttribute("disabled"),
    ).toBe(true);
    expect(mockedFetch).toHaveBeenCalledTimes(1);
  });
});
