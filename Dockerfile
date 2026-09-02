FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml alembic.ini ./
COPY migrations ./migrations
COPY src ./src
RUN pip install --no-cache-dir .

RUN groupadd --gid 10002 channelbot \
    && useradd --uid 10002 --gid channelbot --system --no-create-home channelbot \
    && chown -R channelbot:channelbot /app

USER channelbot

CMD ["python", "-m", "channel_manager_bot"]
