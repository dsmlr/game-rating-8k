# Towards Automated Video Game Age Rating: Bridging Visual and Textual Modalities through Multimodal Fusion

**game-rating-8k** is the dataset used in the paper
[*Towards Automated Video Game Age Rating: Bridging Visual and Textual Modalities through Multimodal Fusion*](https://doi.org/10.1007/978-981-92-8137-4_29)
(see [Citation](#citation)).

It contains 8,830 games labelled with their ESRB rating (5 classes), used for multimodal ESRB rating prediction.

| E | E10 | T | M | AO | total |
|---|---|---|---|---|---|
| 2,000 | 2,000 | 2,000 | 2,000 | 830 | 8,830 |

Sources: IGDB (8,014 games), JAST (657), EROLAB (159).

## Files

- `games.parquet`: the main table, one row per game
  - `game_id`: dataset id (for IGDB games this equals the IGDB game id; JAST = 600001+, EROLAB = 700001+)
  - `igdb_id`: IGDB game id (null for non-IGDB games)
  - `name`, `data_source`, `ESRB`, `release_year`, `release_month`
- `summary.parquet`: game summaries (`game_id`, `data_source`, `summary`, `summary_clean`)
- `storyline.parquet`: game storylines (`game_id`, `data_source`, `storyline`, `storyline_clean`)
  - both ship with the JAST / EROLAB games only; IGDB rows are added by `fetch_igdb_text.py`
  - `*_clean` is the preprocessed text used in the experiments (lowercase, stopwords removed, lemmatized)
  - EROLAB pages have no separate story section, so their storyline is the same as their summary
- `fetch_igdb_text.py`: downloads `summary` and `storyline` for the IGDB games via the IGDB API
  and adds them to `summary.parquet` / `storyline.parquet`
- `screenshots.parquet`: one row per screenshot (60,282), linked to `games.parquet` by `game_id`
  - `screenshot_id`: for IGDB rows this is the IGDB screenshot id
  - `data_source`
  - `file`: path of the image file (`screenshots/<source>_<screenshot_id>.jpg`), created by
    `extract_screenshots.py` (JAST / EROLAB) or `fetch_igdb_screenshots.py` (IGDB)
  - `source_url`: original image URL (JAST / EROLAB only)
  - `width`, `height`: size of the original image (the image files are resized to 480x480)
- `captions.parquet`: one row per screenshot (60,282), for all sources including IGDB
  - `screenshot_id`, `game_id`, `data_source`
  - `caption`: original caption generated with LLaVA-7B (8 screenshots have an empty caption)
  - `revised_caption`: manually reviewed and/or name-masked version of the caption
    (11,277 screenshots, null otherwise); see [Captions](#captions).
    Use `revised_caption` when present, else `caption`: `df.revised_caption.fillna(df.caption)`
- `screenshots_JAST_EROLAB/part-*.parquet`: the 6,764 JAST / EROLAB screenshots as raw JPEG bytes
  (columns `screenshot_id`, `game_id`, `data_source`, `file`, `image_bytes`)
- `extract_screenshots.py`: writes those images to `screenshots/`
- `fetch_igdb_screenshots.py`: downloads the IGDB screenshots into `screenshots/` via the IGDB API

## JAST / EROLAB screenshots

The screenshots of the JAST and EROLAB games are stored as image bytes inside parquet files.

```bash
python extract_screenshots.py            # -> screenshots/JAST_xxx.jpg, screenshots/EROLAB_xxx.jpg
```

Or load them directly without writing files:

```python
import io, pandas as pd
from PIL import Image
df = pd.read_parquet("screenshots_JAST_EROLAB")          # reads all parts
img = Image.open(io.BytesIO(df.image_bytes[0]))
```

## Getting the text

IGDB game descriptions are not redistributed here, in line with the
[IGDB / Twitch terms](https://api-docs.igdb.com/#about). Download them with your own API credentials:

1. Create a Twitch application: https://dev.twitch.tv/console/apps (see https://api-docs.igdb.com/#account-creation)
2. Run:

```bash
pip install -r requirements.txt
export TWITCH_CLIENT_ID=your_client_id
export TWITCH_CLIENT_SECRET=your_client_secret
python fetch_igdb_text.py           # adds the IGDB rows to summary.parquet / storyline.parquet
python fetch_igdb_text.py --clean   # also fills summary_clean / storyline_clean for those rows
```

Notes:
- IGDB content changes over time, so the downloaded text may differ slightly from what was used in the paper,
  and some games may have been removed (the script prints a warning for missing ids).
- `--clean` approximates the experiment preprocessing (lowercase, stopword removal, lemmatization).
- Without `--clean`, `*_clean` is null for the IGDB rows.
- The JAST / EROLAB rows are kept as they are; re-running the script replaces only the IGDB rows.

## Getting the IGDB screenshots

IGDB screenshots are not redistributed either. With the same credentials as above:

```bash
python fetch_igdb_screenshots.py            # -> screenshots/IGDB_<screenshot_id>.jpg (480x480)
python fetch_igdb_screenshots.py --size 0   # keep the original resolution
```

Already downloaded files are skipped, so the script can be re-run to resume. Screenshots that have since
been removed from IGDB are reported at the end.

## Captions

Captions were generated with LLaVA-7B from each screenshot and then processed as follows:

- **Manual review:** 10,064 captions were manually reviewed and corrected.
- **Rating mentions:** no caption mentions an age rating, rating board or age gate
  (e.g. "rated M", "ESRB", "18+").
- **Game names:** titles of games in the dataset, including other games (e.g. "likely Call of Duty"),
  were replaced with `[NAME]` (1,264 screenshots). Matching is case-sensitive on the title words,
  so ordinary words are kept ("the forest"), but a few proper nouns that share a name with a game
  are also masked (e.g. "World War II"). Character names that are not part of a game title
  (e.g. "Mario") are not masked.

Both the manual corrections and the name masking are stored in `revised_caption`; `caption` keeps the
original LLaVA-7B output.

## Citation

If you use this dataset in your research, we kindly ask that you cite the following paper:

```bibtex
@inproceedings{jintawatsakoon2027towards,
  author    = {Jintawatsakoon, Supanat and Pasupa, Kitsuchart},
  title     = {Towards Automated Video Game Age Rating: Bridging Visual and Textual Modalities Through Multimodal Fusion},
  booktitle = {Neural Information Processing},
  series    = {Communications in Computer and Information Science},
  volume    = {3201},
  chapter   = {29},
  publisher = {Springer},
  year      = {2027},
  doi       = {10.1007/978-981-92-8137-4_29},
  url       = {https://doi.org/10.1007/978-981-92-8137-4_29}
}
```
