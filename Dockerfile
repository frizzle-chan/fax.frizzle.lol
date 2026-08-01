FROM docker.io/library/python:3.14.5-trixie AS production
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
LABEL org.opencontainers.image.source=https://github.com/frizzle-chan/fax.frizzle.lol

# Pinned, not :latest — `uv sync --locked` is only reproducible if uv is too.
COPY --from=ghcr.io/astral-sh/uv:0.9.18 /uv /uvx /bin/

RUN mkdir -p /usr/share/fonts/truetype/unifontex \
 && curl -sSL \
      -o /usr/share/fonts/truetype/unifontex/unifontex.ttf \
      https://github.com/stgiga/UnifontEX/releases/download/15.1jan23morePona/UnifontExMono.ttf

# Create a non-root user named fax and switch to it
RUN groupadd --gid 1000 fax-frizzle \
 && useradd --uid 1000 --gid 1000 -m fax-frizzle --shell /bin/bash \
 && mkdir -p /app \
 && chown fax-frizzle:fax-frizzle /app

USER fax-frizzle

WORKDIR /app

ENV UV_NO_DEV=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_CACHE_DIR=/home/fax-frizzle/.cache/uv/ \
    PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PATH=/app/.venv/bin:/home/fax-frizzle/.local/bin:$PATH

# Install dependencies
RUN --mount=type=cache,target=/home/fax-frizzle/.cache/uv,uid=1000,gid=1000 \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

COPY . .

RUN --mount=type=cache,target=/home/fax-frizzle/.cache/uv,uid=1000,gid=1000 \
    uv sync --locked

CMD [ "python", "bot.py" ]

FROM production AS devcontainer

ENV UV_NO_DEV=0 \
    UV_COMPILE_BYTECODE=0 \
    UV_NO_CACHE=0 \
    UV_LINK_MODE=copy

USER root

# install stuff
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
       curl \
       git \
       just \
       procps \
       sqlite3 \
       vim \
       zsh \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/* \
 && chsh -s /bin/zsh fax-frizzle

USER fax-frizzle
