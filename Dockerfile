# wiki-kit: one image that lints, builds, and serves brain-* bundles.
# Step 4 scope: lint/validate toolchain. Node/Quartz land at step 5,
# builder loop at step 6, MCP at step 9.
FROM python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY scripts/ scripts/
COPY template/ template/
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh scripts/*.py

ENTRYPOINT ["/app/entrypoint.sh"]
