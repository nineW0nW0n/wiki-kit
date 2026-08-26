# wiki-kit: one image that lints, builds, and serves brain-* bundles.
# Builder loop lands at step 6, MCP at step 9.
FROM python:3.12-slim@sha256:7a8b475003c4fe15a2cd4e55e5cfc2f3560bdc9333d624f24cdd6d4340fd7a17

ARG QUARTZ_TAG=v5.0.0
ARG NODE_MAJOR=22

# git for bundle pulls; Node 22 (Quartz 5 needs node>=22, npm>=10.9.2) via
# NodeSource, pinned to the major.
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends git ca-certificates curl gnupg \
    && curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get purge -y curl gnupg \
    && rm -rf /var/lib/apt/lists/*

# Quartz pinned by tag; deps and community plugins (pinned by commit in
# quartz.lock.json) install at image build so runtime needs no network.
RUN git clone --depth 1 -b "$QUARTZ_TAG" https://github.com/jackyzha0/quartz /opt/quartz \
    && cd /opt/quartz \
    && npm ci \
    && npx quartz plugin install \
    && npm cache clean --force

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY scripts/ scripts/
COPY mcp/ mcp/
COPY template/ template/
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh scripts/*.py

ENTRYPOINT ["/app/entrypoint.sh"]
