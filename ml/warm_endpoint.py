"""Warm a deployed SageMaker endpoint with a representative JPEG request."""

import argparse
import json
import os
import time
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint-name", default=os.environ.get("SAGEMAKER_ENDPOINT_NAME"))
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "ap-south-1"))
    return parser.parse_args()


def main():
    args = parse_args()
    if not args.endpoint_name:
        raise ValueError("--endpoint-name or SAGEMAKER_ENDPOINT_NAME is required")

    import boto3
    from botocore.config import Config

    image_bytes = args.image.read_bytes()
    started_at = time.perf_counter()
    client = boto3.client(
        "sagemaker-runtime",
        region_name=args.region,
        config=Config(connect_timeout=3, read_timeout=20, retries={"max_attempts": 1}),
    )
    response = client.invoke_endpoint(
        EndpointName=args.endpoint_name,
        ContentType="image/jpeg",
        Accept="application/json",
        Body=image_bytes,
    )
    payload = json.loads(response["Body"].read())
    print(json.dumps({"latency_ms": round((time.perf_counter() - started_at) * 1000), "response": payload}, indent=2))


if __name__ == "__main__":
    main()
