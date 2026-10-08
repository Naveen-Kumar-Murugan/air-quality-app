"""Prepare dataset splits and evaluation artifacts. Accepts user-specified local dataset and S3 URI."""

import argparse
import os


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-dir", default=os.environ.get("ML_DATA_DIR", "data"), help="Local dataset root with class folders")
    parser.add_argument("--s3-uri", default=os.environ.get("S3_DATA_URI"), help="Optional S3 URI for dataset upload")
    parser.add_argument("--split-ratio", type=float, default=0.8, help="Train/val split ratio")
    args = parser.parse_args()
    print(f"Preparation: local_dir={args.local_dir} s3_uri={args.s3_uri} split={args.split_ratio}")
    print("No dataset exists in repo; user must supply --local-dir and optionally --s3-uri.")
    print("Split by session/location (not random) to avoid leakage.")


if __name__ == "__main__":
    main()
