# syntax=docker/dockerfile:1

# SDO Forecast MCP server image. The database is rebuilt from the committed
# snapshots in data/raw/ while the image is built; no state agency is contacted.
# The image carries the compact served-totals database, the same content as a
# compressed database release, not the full age/sex/race research build.
#
#   docker build -t sdo-mcp .
#   docker run -i --rm sdo-mcp

ARG PYTHON_IMAGE=python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258
ARG UV_VERSION=0.11.32

# ---------------------------------------------------------------- database
# The database file is platform independent, so a multi-platform build makes
# it once on the build machine instead of once per target under emulation.
FROM --platform=$BUILDPLATFORM ${PYTHON_IMAGE} AS database
ARG UV_VERSION
# Recorded in the database and reported by list_states as database_release.
ARG DATABASE_RELEASE=image-local
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 \
    UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy
RUN pip install "uv==${UV_VERSION}"
WORKDIR /src
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-default-groups --group ingest --no-install-project
COPY src ./src
COPY data/raw ./data/raw
# Rebuild the full database (input fingerprints are checked), reduce it to
# the served totals with the release command (which compares both copies),
# then install the archive through the same checks a user's install runs.
RUN uv sync --locked --no-default-groups --group ingest \
 && uv run --no-sync python -m sdo_mcp.ingest.build /build/full.sqlite \
 && uv run --no-sync python -m sdo_mcp.release /build/full.sqlite \
      --output /build/releases --version "${DATABASE_RELEASE}" \
 && release=/build/releases/${DATABASE_RELEASE} \
 && sha256=$(python -c 'import json,sys; print(json.load(open(sys.argv[1]))["sha256"])' "$release/manifest.json") \
 && uv run --no-sync python -m sdo_mcp.install "$release/sdo-${DATABASE_RELEASE}.sqlite.gz" \
      --sha256 "$sha256" --destination /out/sdo.sqlite

# --------------------------------------------------------------- server env
# Only the serving dependencies, installed from the lock file for the target
# platform. The ingest libraries and source snapshots stay out of the image.
FROM ${PYTHON_IMAGE} AS app
ARG UV_VERSION
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 \
    UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/sdo-mcp
RUN pip install "uv==${UV_VERSION}"
WORKDIR /src
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-default-groups --no-install-project
COPY src ./src
RUN uv sync --locked --no-default-groups --no-editable

# ------------------------------------------------------------------ runtime
FROM ${PYTHON_IMAGE}
LABEL org.opencontainers.image.title="SDO Forecast MCP" \
      org.opencontainers.image.description="MCP server for state demography office population, household, and employment forecasts" \
      org.opencontainers.image.source="https://github.com/LizzleChen/sdo-mcp"
RUN useradd --system --no-create-home --shell /usr/sbin/nologin sdo \
 && install -d -m 0755 /usr/local/share/sdo-mcp
COPY --from=app /opt/sdo-mcp /opt/sdo-mcp
COPY --from=database --chmod=0444 /out/sdo.sqlite /usr/local/share/sdo-mcp/sdo.sqlite
ENV PATH=/opt/sdo-mcp/bin:$PATH \
    SDO_DB=/usr/local/share/sdo-mcp/sdo.sqlite \
    PYTHONUNBUFFERED=1
USER sdo
# MCP over stdio: run with `docker run -i`.
ENTRYPOINT ["sdo-mcp"]
