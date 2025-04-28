FROM python:3.11-slim as base
WORKDIR /app

# Install pipx (tooling: poetry)
RUN pip3 install --user pipx
ENV PATH=/root/.local/bin:$PATH
RUN pipx ensurepath

RUN apt update && \
    apt install -y \
        build-essential \
        openssh-client \
        libssl-dev \
        libffi-dev \
        python3-dev \
        ssh \
        curl \
        pkg-config \
        libudev-dev \
        git && \
    rm -rf /var/lib/apt/lists/*
RUN mkdir -p -m 0600 ~/.ssh && ssh-keyscan github.com >> ~/.ssh/known_hosts

# Get the python environment setup using poetry
RUN pipx install poetry
RUN poetry config virtualenvs.create true
RUN poetry config virtualenvs.in-project true

# Install python dependencies
COPY poetry.lock /app/poetry.lock
COPY pyproject.toml /app/pyproject.toml
COPY volsync_operator /app/volsync_operator
COPY README.md /app/README.md
RUN --mount=type=ssh poetry install --only=main --no-interaction --no-ansi

FROM python:3.11-slim as final

RUN apt update && \
    apt install -y \
        libudev1 \
        && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=base /app .
ENV PATH /app/.venv/bin:/root/.cargo/bin:/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# Add -vvv after poetry to debug poetry
ENTRYPOINT ["python3","-m", "kopf", "run"]
# Add --verbose or even --debug to see more output from kopf 
CMD [ "--liveness=http://0.0.0.0:8080/healthz", "--standalone", "--all-namespaces", "-m", "volsync_operator"]

