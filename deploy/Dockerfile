FROM python:3.11-slim

ARG VCS_REF=unknown
ARG VERSION=0.0.0-dev

LABEL org.opencontainers.image.source="https://github.com/Lochy2000/Cloud-based-architecture-Digital-Twin" \
      org.opencontainers.image.description="Python runtime for the cloud-based thermal-asset digital twin" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.licenses="NOASSERTION"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

WORKDIR /app

COPY requirements-runtime.txt .
RUN python -m pip install --no-cache-dir -r requirements-runtime.txt

RUN groupadd --gid 10001 twin \
    && useradd --uid 10001 --gid twin --create-home --shell /usr/sbin/nologin twin

COPY --chown=twin:twin src/ /app/src/

USER 10001:10001

CMD ["python", "-m", "twin.publisher"]
