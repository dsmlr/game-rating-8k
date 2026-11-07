#!/usr/bin/env python3
"""Download `summary` and `storyline` from the IGDB API for the IGDB games in games.parquet,
and add them to summary.parquet / storyline.parquet.

IGDB text is not redistributed in this repository; run this script to rebuild it locally.
summary.parquet and storyline.parquet ship with the JAST / EROLAB games only; this script
adds (or replaces) the rows of the IGDB games and keeps the JAST / EROLAB rows untouched.

Requirements: a Twitch developer application (https://dev.twitch.tv/console/apps),
see https://api-docs.igdb.com/#account-creation. Set the credentials as env vars:

    export TWITCH_CLIENT_ID=...
    export TWITCH_CLIENT_SECRET=...
    python fetch_igdb_text.py                    # updates summary.parquet / storyline.parquet
    python fetch_igdb_text.py --clean            # also fills summary_clean / storyline_clean for IGDB rows
"""
import argparse
import os
import re
import sys
import time

import pandas as pd
import requests

TOKEN_URL = "https://id.twitch.tv/oauth2/token"
GAMES_URL = "https://api.igdb.com/v4/games"
BATCH_SIZE = 500          # IGDB max limit per request
REQUEST_INTERVAL = 0.3    # IGDB allows 4 requests / second
MAX_RETRIES = 5


def get_access_token(client_id, client_secret):
    resp = requests.post(TOKEN_URL, params={
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials",
    }, timeout=30)
    resp.raise_for_status()
    return resp.json()["access_token"]


def fetch_batch(ids, headers):
    body = (
        "fields id,name,summary,storyline; "
        f"where id = ({','.join(map(str, ids))}); "
        f"limit {BATCH_SIZE};"
    )
    for attempt in range(MAX_RETRIES):
        resp = requests.post(GAMES_URL, headers=headers, data=body, timeout=60)
        if resp.status_code == 429 or resp.status_code >= 500:
            time.sleep(2 ** attempt)
            continue
        resp.raise_for_status()
        return resp.json()
    resp.raise_for_status()


def fetch_igdb_text(igdb_ids, client_id, client_secret):
    headers = {
        "Client-ID": client_id,
        "Authorization": f"Bearer {get_access_token(client_id, client_secret)}",
        "Accept": "application/json",
    }
    rows = []
    for start in range(0, len(igdb_ids), BATCH_SIZE):
        batch = igdb_ids[start:start + BATCH_SIZE]
        rows.extend(fetch_batch(batch, headers))
        print(f"  fetched {min(start + BATCH_SIZE, len(igdb_ids))}/{len(igdb_ids)}", file=sys.stderr)
        time.sleep(REQUEST_INTERVAL)
    df = pd.DataFrame(rows, columns=["id", "name", "summary", "storyline"])
    return df.rename(columns={"id": "igdb_id", "name": "igdb_name"})


def make_cleaner():
    """Approximation of the preprocessing used in the experiments:
    lowercase, tokenize, drop stopwords/punctuation, POS-aware lemmatization (NLTK)."""
    import nltk
    from nltk.corpus import stopwords
    from nltk.stem import WordNetLemmatizer

    for pkg in ["punkt", "punkt_tab", "stopwords", "wordnet",
                "averaged_perceptron_tagger", "averaged_perceptron_tagger_eng"]:
        nltk.download(pkg, quiet=True)

    stop = set(stopwords.words("english"))
    lemmatizer = WordNetLemmatizer()
    pos_map = {"J": "a", "V": "v", "N": "n", "R": "r"}

    def clean(text):
        if not isinstance(text, str) or not text.strip():
            return ""
        text = re.sub(r"<[^>]+>", " ", text).lower()
        tokens = nltk.word_tokenize(text)
        out = []
        for tok, tag in nltk.pos_tag(tokens):
            if tok in stop or not re.search(r"[a-z0-9]", tok):
                continue
            out.append(lemmatizer.lemmatize(tok, pos_map.get(tag[0], "n")))
        return " ".join(out)

    return clean


def update_text_file(path, igdb_games, column, clean):
    """Replace the IGDB rows of summary.parquet / storyline.parquet, keep the other sources."""
    new = igdb_games[["game_id", "data_source", column]].copy()
    new[f"{column}_clean"] = new[column].map(clean) if clean else None
    old = pd.read_parquet(path)
    old = old[old["data_source"] != "IGDB"]
    out = pd.concat([old, new], ignore_index=True).sort_values("game_id").reset_index(drop=True)
    out.to_parquet(path, index=False)
    print(f"Saved {len(out)} rows ({len(new)} IGDB) -> {path}", file=sys.stderr)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--games", default=os.path.join(here, "games.parquet"))
    parser.add_argument("--summary", default=os.path.join(here, "summary.parquet"))
    parser.add_argument("--storyline", default=os.path.join(here, "storyline.parquet"))
    parser.add_argument("--clean", action="store_true", help="fill summary_clean / storyline_clean for IGDB rows")
    args = parser.parse_args()

    client_id = os.environ.get("TWITCH_CLIENT_ID")
    client_secret = os.environ.get("TWITCH_CLIENT_SECRET")
    if not client_id or not client_secret:
        sys.exit("Set TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET (see https://api-docs.igdb.com/#account-creation).")

    games = pd.read_parquet(args.games)
    games = games[games["data_source"] == "IGDB"]
    igdb_ids = games["igdb_id"].astype(int).tolist()
    print(f"Fetching text for {len(igdb_ids)} IGDB games ...", file=sys.stderr)

    text = fetch_igdb_text(igdb_ids, client_id, client_secret)
    igdb_games = games[["game_id", "igdb_id", "data_source"]].merge(text, on="igdb_id", how="left")
    igdb_games[["summary", "storyline"]] = igdb_games[["summary", "storyline"]].fillna("")

    missing = sorted(set(igdb_ids) - set(text["igdb_id"]))
    if missing:
        print(f"WARNING: {len(missing)} IGDB ids not returned by the API (removed or merged): "
              f"{missing[:20]}{' ...' if len(missing) > 20 else ''}", file=sys.stderr)

    clean = make_cleaner() if args.clean else None
    update_text_file(args.summary, igdb_games, "summary", clean)
    update_text_file(args.storyline, igdb_games, "storyline", clean)


if __name__ == "__main__":
    main()
