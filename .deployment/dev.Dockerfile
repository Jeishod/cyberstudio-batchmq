########################################################################################################################
FROM python:3.11-slim AS compile-image

ARG BASE_DIR=/app
ARG USER=app
ARG GROUP=app

RUN apt-get update
RUN apt-get install -y --no-install-recommends build-essential gcc curl

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    DOCKER_CONTAINER=1 \
    TZ=UTC

WORKDIR ${BASE_DIR}

RUN adduser --uid 1000 --home ${BASE_DIR} --disabled-password --gecos "" ${USER} \
    && chown -hR ${USER}: ${BASE_DIR}

RUN pip install "poetry"

COPY ./pyproject.toml ./poetry.lock  ${BASE_DIR}

RUN poetry config virtualenvs.in-project true && \
    poetry config virtualenvs.create true && \
    poetry install --no-interaction --no-ansi --without dev

########################################################################################################################
FROM compile-image as dev

COPY --from=compile-image ${BASE_DIR}/.venv  ${BASE_DIR}/.venv

ENV PATH="${BASE_DIR}/.venv/bin:$PATH"
USER ${USER}

CMD ["python", "-m", "uvicorn", "--reload", "--use-colors", "--host", "0.0.0.0", "--port", "8000", "--log-level", "debug", "app.main:app"]
