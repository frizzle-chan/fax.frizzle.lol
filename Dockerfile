FROM docker.io/python:3.13.2-bookworm AS base

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Create a non-root user named fax and switch to it
RUN useradd -ms /bin/bash frizzle
USER frizzle

WORKDIR /app

ENV PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    POETRY_VERSION=2.1.2 \
    POETRY_VIRTUALENVS_CREATE=false \
    PATH=/home/frizzle/.local/bin:$PATH

# install poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

COPY pyproject.toml poetry.lock ./
RUN poetry install --only main

FROM base AS production

COPY . .

FROM base AS development

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# hadolint ignore=DL3002
USER root

ENV PATH=/home/frizzle/.local/bin:$PATH

# Install gh, vim
# hadolint ignore=DL3008,DL3015,SC2016
RUN curl -sS -o "/etc/apt/keyrings/githubcli-archive-keyring.gpg" https://cli.github.com/packages/githubcli-archive-keyring.gpg \
 && chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
 && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
 && apt-get update \
 && apt-get install -y \
        gh \
        vim \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# Configure shell
COPY .devcontainer/starship.toml /root/.config/starship.toml
# hadolint ignore=SC2016
RUN curl -sS -o /tmp/install-starship.sh https://starship.rs/install.sh \
 && sh /tmp/install-starship.sh --yes \
 && rm /tmp/install-starship.sh \
 && echo 'eval "$(starship init bash)"' >> /root/.bashrc \
 && echo 'export EDITOR=vim' >> /root/.bashrc \
 && echo 'set -o vi' >> /root/.bashrc

RUN poetry install