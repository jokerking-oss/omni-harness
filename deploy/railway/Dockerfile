# API-only image for Railway: the Gateway plus the embedded agent runtime.
#
# The Next.js frontend is deployed separately (Vercel) and reaches this service
# through a same-origin rewrite, so the browser never talks to this origin
# directly and no CORS configuration is required. That also keeps the auth
# cookie first-party: it is hardcoded `SameSite=Lax`, which would be dropped on
# a genuinely cross-site request (e.g. *.vercel.app -> *.up.railway.app).
#
# Deliberately omitted versus backend/Dockerfile:
#   - Node.js and the Lark CLI (the managed Lark integration needs them)
#   - any compiler toolchain: the runtime installs wheels only
#
# Persistent state lives under OMNI_HARNESS_HOME; mount a Railway volume there or
# every redeploy starts from an empty database.

FROM ghcr.io/astral-sh/uv:0.11.1 AS uv

FROM python:3.12-slim-bookworm

COPY --from=uv /uv /uvx /usr/local/bin/

ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    OMNI_HARNESS_PROJECT_ROOT=/app \
    OMNI_HARNESS_CONFIG_PATH=/app/config.yaml \
    OMNI_HARNESS_EXTENSIONS_CONFIG_PATH=/app/extensions_config.json \
    OMNI_HARNESS_HOME=/app/backend/.omni-harness

WORKDIR /app

COPY backend /app/backend
COPY contracts /app/contracts
COPY skills /app/skills
COPY deploy/railway/config.yaml /app/config.yaml

# The Gateway rewrites this file at runtime, so it must exist and be writable.
RUN printf '{}\n' > /app/extensions_config.json \
    && cd /app/backend && uv sync --locked --all-packages

EXPOSE 8001

# Railway injects PORT; fall back to the Gateway's usual 8001 for local runs.
CMD ["sh", "-c", "cd /app/backend && PYTHONPATH=. uv run --no-sync uvicorn app.gateway.app:app --host 0.0.0.0 --port ${PORT:-8001}"]
