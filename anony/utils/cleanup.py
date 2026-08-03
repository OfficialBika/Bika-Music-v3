import os
import time

DOWNLOAD_DIR = "downloads"
MP4_MAX_AGE = 24 * 60 * 60
MP3_MAX_AGE = 3 * 24 * 60 * 60

async def cleanup_downloads():
    if not os.path.exists(DOWNLOAD_DIR):
        return

    now = time.time()
    deleted = 0

    for filename in os.listdir(DOWNLOAD_DIR):
        path = os.path.join(DOWNLOAD_DIR, filename)
        if not os.path.isfile(path):
            continue

        age = now - os.path.getmtime(path)

        if filename.lower().endswith('.mp4') and age > MP4_MAX_AGE:
            os.remove(path)
            deleted += 1
        elif filename.lower().endswith('.mp3') and age > MP3_MAX_AGE:
            os.remove(path)
            deleted += 1

    return deleted
