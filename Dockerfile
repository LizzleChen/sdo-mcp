# syntax=docker/dockerfile:1

# SDO Forecast MCP server image. The database is rebuilt from the committed
# snapshots in data/raw/ while the image is built; no state agency is contacted.
# The served totals are bundled into the package exactly as for a wheel
# release, so the image carries the same data, not the full age/sex/race build.
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
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 \
    UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy
RUN pip install "uv==${UV_VERSION}"
WORKDIR /src
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-default-groups --group ingest --no-install-project
COPY hatch_build.py ./
COPY src ./src
COPY data/raw ./data/raw
# Rebuild the full database (input fingerprints are checked), then bundle the
# served totals, which compares both copies and records the package version.
RUN uv sync --locked --no-default-groups --group ingest \
 && uv run --no-sync python -m sdo_mcp.ingest.build /build/full.sqlite \
 && uv run --no-sync python -m sdo_mcp.bundle /build/full.sqlite

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
COPY hatch_build.py ./
COPY src ./src
COPY --from=database /src/src/sdo_mcp/data/sdo.sqlite ./src/sdo_mcp/data/sdo.sqlite
# A non-editable install builds the wheel, which carries the bundled data.
RUN uv sync --locked --no-default-groups --no-editable

# ------------------------------------------------------------------ runtime
FROM ${PYTHON_IMAGE}
LABEL org.opencontainers.image.title="SDO Forecast MCP" \
      org.opencontainers.image.description="MCP server for state demography office population, household, and employment forecasts" \
      org.opencontainers.image.source="https://github.com/LizzleChen/sdo-mcp"
RUN useradd --system --no-create-home --shell /usr/sbin/nologin sdo
COPY --from=app /opt/sdo-mcp /opt/sdo-mcp
ENV PATH=/opt/sdo-mcp/bin:$PATH \
    PYTHONUNBUFFERED=1
USER sdo
# MCP over stdio: run with `docker run -i`.
ENTRYPOINT ["sdo-mcp"]
