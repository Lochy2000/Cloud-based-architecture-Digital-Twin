# https://docs.docker.com/get-started/docker-concepts/building-images/writing-a-dockerfile/
FROM python:3.11-slim

# unbuffered stdout: without this, Python buffers output and log timestamps
# lag events. 
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1


WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ /app/src/
ENV PYTHONPATH=/app/src

# non-root: the container writes nothing to disk.
RUN useradd --create-home --shell /bin/false twin
USER twin

# overridden per service in docker-compose.yml.
CMD ["python", "-m", "twin.publisher"]