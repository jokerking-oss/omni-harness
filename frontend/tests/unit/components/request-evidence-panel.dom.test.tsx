import { afterEach, beforeEach, expect, it, rs } from "@rstest/core";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";

import { RequestEvidencePanel } from "@/components/workspace/request-evidence-panel";
import { enUS } from "@/core/i18n/locales/en-US";
import { fetchRequestEvidence } from "@/core/messages/request-evidence";

rs.mock("@/core/i18n/hooks", () => ({ useI18n: () => ({ t: enUS }) }));
rs.mock("@/core/auth/AuthProvider", () => ({
  useAuth: () => ({ user: { id: "u" } }),
}));
rs.mock("@/core/messages/request-evidence", () => ({
  fetchRequestEvidence: rs.fn(),
}));

beforeEach(() => {
  rs.mocked(fetchRequestEvidence).mockReset();
});
afterEach(cleanup);

it("loads evidence only on expansion and distinguishes provider from model input", async () => {
  rs.mocked(fetchRequestEvidence).mockResolvedValue({
    events: ["provider_payload", "model_input"].map((boundary, index) => ({
      seq: index + 1,
      metadata: { caller: "lead_agent", llm_call_index: index + 1 },
      content: {
        version: 1,
        boundary: boundary as "provider_payload" | "model_input",
        sha256: "a".repeat(64),
        bytes: 100,
        message_count: 2,
        tool_count: 0,
        tools: [],
        components: [],
        delta: { added: 1, removed: 0, reused: 1, bytes: -20 },
        truncated: false,
      },
    })),
  });
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const { container } = render(
    <QueryClientProvider client={client}>
      <RequestEvidencePanel threadId="t" runId="r" />
    </QueryClientProvider>,
  );
  expect(fetchRequestEvidence).not.toHaveBeenCalled();
  const details = container.querySelector("details")!;
  details.open = true;
  fireEvent(details, new Event("toggle"));
  await waitFor(() =>
    expect(screen.getByText(enUS.requestEvidence.providerPayload)).toBeTruthy(),
  );
  expect(screen.getByText(enUS.requestEvidence.modelInput)).toBeTruthy();
  expect(screen.getByText(enUS.requestEvidence.description)).toBeTruthy();
  client.clear();
});
