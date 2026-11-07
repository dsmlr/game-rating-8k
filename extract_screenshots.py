#!/usr/bin/env python3
"""Extract the JAST / EROLAB screenshots stored in screenshots_JAST_EROLAB/*.parquet into image files.

    python extract_screenshots.py                 # -> screenshots/JAST_xxx.jpg, screenshots/EROLAB_xxx.jpg
    python extract_screenshots.py --out-dir /data/esrb

Files are written to <out-dir>/<file>, where `file` matches the `file` column of screenshots.parquet.
"""
import argparse
import glob
import os
import sys

import pyarrow.parquet as pq


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--src", default=os.path.join(here, "screenshots_JAST_EROLAB"),
                        help="folder containing part-*.parquet")
    parser.add_argument("--out-dir", default=here, help="base folder; images go to <out-dir>/screenshots/")
    parser.add_argument("--overwrite", action="store_true", help="overwrite existing files")
    args = parser.parse_args()

    parts = sorted(glob.glob(os.path.join(args.src, "part-*.parquet")))
    if not parts:
        sys.exit(f"No part-*.parquet found in {args.src}")

    written = skipped = 0
    for part in parts:
        pf = pq.ParquetFile(part)
        for batch in pf.iter_batches(columns=["file", "image_bytes"], batch_size=256):
            for rel_path, data in zip(batch.column("file").to_pylist(), batch.column("image_bytes").to_pylist()):
                path = os.path.join(args.out_dir, rel_path)
                if os.path.exists(path) and not args.overwrite:
                    skipped += 1
                    continue
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as f:
                    f.write(data)
                written += 1
        print(f"  {os.path.basename(part)} done", file=sys.stderr)

    print(f"Wrote {written} images, skipped {skipped} existing -> {os.path.join(args.out_dir, 'screenshots')}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
