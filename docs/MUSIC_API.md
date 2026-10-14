# Bika Music API — Voice Chat playback

This optional API separates search metadata from audio delivery. It lets the existing PyTgCalls player stream from a local, authorized audio catalog without sending a long-lived API key to FFmpeg.

## Important limitation

The official YouTube Data API returns video metadata and watch links; it does not return a direct audio stream. The endpoint `/api/v1/youtube/search` is metadata-only. Voice-chat playback in API-only mode comes from files you are authorized to stream from the local audio catalog. This service intentionally does not turn YouTube cookies into audio URLs or bypass YouTube playback/download controls.

Only add audio to the catalog when you have the rights or permission needed to stream it.

## Endpoints

- `GET /healthz` — health check, no API key required.
- `GET /api/v1/youtube/search?q=...&limit=5` — official YouTube metadata search. Requires `X-API-Key`.
- `GET /api/v1/library/search?q=...&limit=5` — search the authorized local audio catalog. Requires `X-API-Key`.
- `GET /api/v1/library/{track_id}/stream?expires=...&sig=...` — time-limited signed audio stream. The signature replaces the long-lived API key for FFmpeg.

The catalog scans supported audio files only and ignores symlinks. It uses FFprobe to establish duration before marking an item playable. Install FFmpeg/FFprobe on the API server.

## Run on the same VPS as the bot

Create separate strong secrets with Python:

    python -c 'import secrets; print(secrets.token_urlsafe(48))'

Set the generated values in environment variables or in a private `.env` file:

    YOUTUBE_API_KEY=<Google Cloud YouTube Data API v3 key>
    MUSIC_API_KEY=<random secret, at least 32 characters>
    MUSIC_API_SIGNING_SECRET=<a different random secret, at least 32 characters>
    MUSIC_API_HOST=127.0.0.1
    MUSIC_API_PORT=8765
    MUSIC_API_AUDIO_DIR=/srv/bika-music/authorized_audio
    MUSIC_API_PUBLIC_BASE_URL=http://127.0.0.1:8765
    MUSIC_API_STREAM_TTL=86400

Start the API from the repository root:

    python -m music_api

The bind address defaults to loopback so the API is not publicly exposed. If the API or bot runs in another container/host, set `MUSIC_API_URL` to an address reachable by the bot and set `MUSIC_API_PUBLIC_BASE_URL` to an address reachable by FFmpeg on the bot host. Do not expose this service publicly without HTTPS, a firewall, and a strong API key.

Put licensed/authorized audio files under the configured audio directory. That directory is intentionally ignored by Git and Docker builds; mount it as persistent storage rather than committing audio to the repository.

## Enable API-only playback in Bika Music

Add these to the bot's private environment file:

    MUSIC_API_URL=http://127.0.0.1:8765
    MUSIC_API_KEY=<the same MUSIC_API_KEY used by the API>
    MUSIC_API_ONLY=true

Restart the bot after updating the private environment. In this mode, the bot's `/play <query>` and voice-chat queue search only the authorized local catalog. If a song is not present in that catalog, the bot will not fall back to extracting audio from a YouTube URL. Keep `MUSIC_API_ONLY=false` to preserve the existing default downloader behavior; that legacy path is separate from the secure API-only mode.

The YouTube metadata endpoint can find a video, but it cannot make that YouTube video directly playable in a Telegram voice chat. A licensed source or a local file you are allowed to stream is needed for audio playback.

## Example requests

    curl http://127.0.0.1:8765/healthz
    curl -H 'X-API-Key: YOUR_MUSIC_API_KEY' \
      'http://127.0.0.1:8765/api/v1/library/search?q=track&limit=5'
    curl -H 'X-API-Key: YOUR_MUSIC_API_KEY' \
      'http://127.0.0.1:8765/api/v1/youtube/search?q=artist%20song&limit=5'

The library response includes a short-lived `source_url`. Treat it like a temporary bearer credential and do not paste it into public logs or chat.

## Validation

Run:

    python -m unittest discover -s tests -v

These tests cover query normalization, signed URL validation, and catalog path/extension handling. They do not replace a live Telegram voice-chat smoke test.
