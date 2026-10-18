# Deploying OmniHarness: Vercel frontend + Railway backend

The product is three cooperating pieces: a Next.js frontend, a long-running Python
Gateway (the agent runtime) and — optionally — Redis. Vercel can only host the
first one, so the Gateway runs here on Railway and Vercel proxies `/api/*` to it.

```
browser ──▶ https://<project>.vercel.app            (Next.js, Vercel)
                │  vercel.json rewrites /api/* (and /api/langgraph/*)
                ▼
            https://<service>.up.railway.app        (Gateway, Railway)
                └── volume at /app/backend/.omni-harness  (SQLite, threads, artifacts)
```

Because the browser only ever talks to the Vercel origin, every request is
same-origin: the auth cookie stays first-party, and no CORS or `SameSite=None`
workaround is needed.

## 1. Backend (Railway)

Create one service from this repository:

| Setting | Value |
| --- | --- |
| Source | GitHub → `jokerking-oss/omni-harness` |
| Builder | Dockerfile |
| Dockerfile path | `deploy/railway/Dockerfile` |
| Volume | mount at `/app/backend/.omni-harness` (holds the SQLite database, thread data and artifacts) |
| Networking | generate a public domain |

Environment variables:

| Name | Value | Notes |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | `sk-...` | required; both configured models share it |
| `AUTH_JWT_SECRET` | random 32+ chars | without it a secret is generated and persisted inside the container |
| `GATEWAY_CORS_ORIGINS` | `https://<project>.vercel.app` | only needed if the browser ever calls this origin directly |
| `OMNI_HARNESS_TRUSTED_ORIGINS` | `https://<project>.vercel.app` | auth origin checks |

Redis is not required: this deployment keeps `run_events.backend: memory` and the
in-process stream bridge, which is fine for a single instance.

## 2. Frontend (Vercel)

Import the same repository, with **Root Directory = `frontend`**.

| Environment variable | Value |
| --- | --- |
| `SKIP_ENV_VALIDATION` | `1` |
| `OMNI_HARNESS_INTERNAL_GATEWAY_BASE_URL` | `https://<project>.vercel.app` (self, so SSR calls go back through the rewrite) |
| `OMNI_HARNESS_TRUSTED_ORIGINS` | `https://<project>.vercel.app` |
| `NEXT_PUBLIC_LANGGRAPH_BASE_URL` | leave unset — the default `/api/langgraph` already goes through the rewrite |
| `NEXT_PUBLIC_BACKEND_BASE_URL` | leave unset — same reason |

`vercel.json` in the repository root rewrites `/api/langgraph/*` and `/api/*` to
the Railway service. Update the `destination` host after Railway assigns one.

## 3. First run

1. Open the Vercel URL — it redirects to `/setup` when no admin exists.
2. Create the admin account.
3. Send a message. The Gateway resolves `deepseek-v4-pro` (first entry in
   `deploy/railway/config.yaml`) and answers.

## Known limitations of this deployment

- **Sandbox isolation**: `sandbox.use` is `LocalSandboxProvider`, i.e. file tools
  operate on the container's own filesystem, and `allow_host_bash` is `false`
  (the `bash` tool is not exposed at all). That is the safe default; enable
  `allow_host_bash` only for a fully trusted, single-user deployment.
- **Long streams through the Vercel proxy**: an agent run can stream for minutes.
  If Vercel's proxy closes the connection, the frontend reconnects using the
  run's `Last-Event-ID` cursor and reloads durable state (`stream_replay_gap`).
  If that proves unreliable, give the backend its own subdomain of the same
  registrable domain and point `NEXT_PUBLIC_LANGGRAPH_BASE_URL` at it directly.
- **No Node.js / Lark CLI** in this image, so the managed Lark integration and
  any `npx`-based MCP server will not work here.
