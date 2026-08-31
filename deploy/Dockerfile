FROM python:3.11-slim

# unbuffered stdout: without this, Python buffers output and log timestamps
# lag events. 
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1