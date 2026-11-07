#!/usr/bin/env python3
"""Download the IGDB screenshots listed in screenshots.parquet into screenshots/.

IGDB images are not redistributed in this repository; run this script to rebuild them locally.
Uses the same Twitch credentials as fetch_igdb_text.py:

    export TWITCH_CLIENT_ID=...
    export TWITCH_CLIENT_SECRET=...
    python fetch_igdb_screenshots.py              # -> screenshots/IGDB_<screenshot_id>.jpg, resized to 480x480
    python fetch_igdb_screenshots.py --size 0     # keep the original resolution

By default images are resized to 480x480 (LANCZOS, aspect ratio not preserved), the same
preprocessing as the bundled JAST / EROLAB screenshots.
"""
import argparse
import io
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests
from PIL import Image

from fetch_igdb_text import BATCH_SIZE, MAX_RETRIES, REQUEST_INTERVAL, get_access_token

SCREENSHOTS_URL = "https://api.igdb.com/v4/screenshots"
IMAGE_URL = "https://images.igdb.com/igdb/image/upload/t_original/{image_id}.jpg"


def fetch_image_ids(screenshot_ids, client_id, client_secret):
    """Map IGDB screenshot id -> image_id (needed to build the image URL)."""
    headers = {
        "Client-ID": client_id,
        "Authorization": f"Bearer {get_access_token(client_id, client_secret)}",
        "Accept": "application/json",
    }
    image_ids = {}
    for start in range(0, len(screenshot_ids), BATCH_SIZE):
        batch = screenshot_ids[start:start + BATCH_SIZE]
        body = f"fields id,image_id; where id = ({','.join(map(str, batch))}); limit {BATCH_SIZE};"
        for attempt in range(MAX_RETRIES):
            resp = requests.post(SCREENSHOTS_URL, headers=headers, data=body, timeout=60)
            if resp.status_code == 429 or resp.status_code >= 500:
                time.sleep(2 ** attempt)
                continue
            break
        resp.raise_for_status()
        image_ids.update({row["id"]: row["image_id"] for row in resp.json() if row.get("image_id")})
        print(f"  metadata {min(start + BATCH_SIZE, len(screenshot_ids))}/{len(screenshot_ids)}", file=sys.stderr)
        time.sleep(REQUEST_INTERVAL)
    return image_ids


def download_image(image_id, path, size):
    url = IMAGE_URL.format(image_id=image_id)
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, timeout=60)
            if resp.status_code == 404:
                return False
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content)).convert("RGB")
            if size:
                img = img.resize((size, size), Image.LANCZOS)
            img.save(path)
            return True
        except (requests.RequestException, OSError):
            time.sleep(2 ** attempt)
    return False


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--screenshots", default=os.path.join(here, "screenshots.parquet"))
    parser.add_argument("--out-dir", default=here, help="base folder; images go to <out-dir>/screenshots/")
    parser.add_argument("--size", type=int, default=480, help="resize to SIZE x SIZE; 0 keeps the original")
    parser.add_argument("--workers", type=int, default=8, help="parallel image downloads")
    parser.add_argument("--overwrite", action="store_true", help="re-download existing files")
    args = parser.parse_args()

    client_id = os.environ.get("TWITCH_CLIENT_ID")
    client_secret = os.environ.get("TWITCH_CLIENT_SECRET")
    if not client_id or not client_secret:
        sys.exit("Set TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET (see https://api-docs.igdb.com/#account-creation).")

    shots = pd.read_parquet(args.screenshots)
    shots = shots[shots["data_source"] == "IGDB"]
    shots = shots.assign(path=shots["file"].map(lambda f: os.path.join(args.out_dir, f)))
    todo = shots if args.overwrite else shots[~shots["path"].map(os.path.exists)]
    print(f"{len(shots)} IGDB screenshots, {len(shots) - len(todo)} already present, {len(todo)} to download",
          file=sys.stderr)
    if todo.empty:
        return

    image_ids = fetch_image_ids(todo["screenshot_id"].tolist(), client_id, client_secret)
    os.makedirs(os.path.join(args.out_dir, "screenshots"), exist_ok=True)

    failed = [sid for sid in todo["screenshot_id"] if sid not in image_ids]
    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(download_image, image_ids[row.screenshot_id], row.path, args.size): row.screenshot_id
            for row in todo.itertuples() if row.screenshot_id in image_ids
        }
        for i, fut in enumerate(as_completed(futures), 1):
            if fut.result():
                done += 1
            else:
                failed.append(futures[fut])
            if i % 1000 == 0 or i == len(futures):
                print(f"  images {i}/{len(futures)}", file=sys.stderr)

    print(f"Downloaded {done} images -> {os.path.join(args.out_dir, 'screenshots')}", file=sys.stderr)
    if failed:
        print(f"WARNING: {len(failed)} screenshots unavailable on IGDB (removed or missing): "
              f"{sorted(failed)[:20]}{' ...' if len(failed) > 20 else ''}", file=sys.stderr)


if __name__ == "__main__":
    main()
