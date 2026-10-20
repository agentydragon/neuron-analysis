# Sandbox for one identity-annotation run: prompt, format, schema, video, reference
# image, the renderer, and common image/video packages. No evaluation data.
FROM python:3.12-slim

# Optional extra-ca.crt (git-ignored) lets builds behind a TLS-intercepting proxy trust it;
# the Dockerfile itself always matches the COPY pattern, so the file may be absent.
COPY evals/identity/Dockerfile evals/identity/extra-ca.cr[t] /tmp/ca/
RUN if [ -f /tmp/ca/extra-ca.crt ]; then cp /tmp/ca/extra-ca.crt /usr/local/share/ca-certificates/ && update-ca-certificates; fi
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    PIP_CERT=/etc/ssl/certs/ca-certificates.crt NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt
RUN pip install --no-cache-dir uv && useradd --create-home --shell /bin/bash agent

WORKDIR /workspace
COPY pyproject.toml uv.lock .python-version ./
COPY neuron_tracking/annotations.py neuron_tracking/render.py neuron_tracking/
# Only the renderer is exposed; evaluation and checking code stays out of the image.
RUN sed -i '/^neuron-check\|^neuron-identity\|^neuron-eval-frames/d' pyproject.toml \
    && printf '# Renderer workspace\n' > README.md \
    && UV_PROJECT_ENVIRONMENT=/workspace/.venv uv sync --locked --no-dev
COPY evals/identity/agent-requirements.txt /tmp/agent-requirements.txt
RUN VIRTUAL_ENV=/workspace/.venv uv pip install --no-cache -r /tmp/agent-requirements.txt

COPY tasks/identity/annotate.md tasks/identity/format.md annotations.schema.json ./
COPY data/IMG_6128.AVI data/photo_2026-10-19_14-30-28.jpg ./
RUN mkdir output && chown -R agent:agent /workspace

ENV PATH=/workspace/.venv/bin:$PATH UV_PROJECT_ENVIRONMENT=/workspace/.venv
USER agent
