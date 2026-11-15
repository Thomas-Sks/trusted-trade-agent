FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY ttap ttap
COPY buyer_agent buyer_agent
COPY policies policies
COPY scripts scripts
RUN uv sync --frozen --no-dev
ENV TTAP_DB=/data/ttap.db TTAP_AUDIT=/data/audit.jsonl TTAP_SIGNING_KEY=/data/signing_key.json
EXPOSE 8811
CMD ["uv", "run", "--no-dev", "uvicorn", "ttap.main:app", "--host", "0.0.0.0", "--port", "8811"]
