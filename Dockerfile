FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .

RUN apt-get update -y \
    && apt-get install -y --no-install-recommends ffmpeg curl unzip ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL https://deno.land/install.sh | sh \
    && mkdir -p /usr/local/deno \
    && cp -a /root/.deno/. /usr/local/deno/ \
    && ln -s /usr/local/deno /home/bika-deno

ENV DENO_INSTALL="/usr/local/deno"
ENV PATH="${DENO_INSTALL}/bin:${PATH}"

RUN pip3 install --no-cache-dir -U pip \
    && pip3 install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --system --create-home --home-dir /home/bikamusic bikamusic \
    && mkdir -p /app/downloads /app/anony/cookies /app/migration_backups \
    && mkdir -p /home/bika \
    && ln -s /usr/local/deno /home/bika/.deno \
    && chown -R bikamusic:bikamusic /app /usr/local/deno /home/bika

USER bikamusic

HEALTHCHECK --interval=60s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import os,sys; sys.exit(0 if os.path.exists('/app/log.txt') else 1)" || exit 1

CMD ["python", "-m", "anony"]
