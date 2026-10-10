#!/usr/bin/env python3
"""Pre-demo warm-up: hit the scan pipeline and coach so nothing is cold on stage.

Runs, in order:
  1. GET /map health (or the API root) to warm the HTTP API + map Lambda.
  2. One SageMaker warm inference via ml/warm_endpoint.py (skipped without --image).
  3. One coach call to warm the Bedrock path (template fallback still counts).

Usage:
    python warm_demo.py --api-base https://<api-id>.execute-api.<region>.amazonaws.com \\
        --token <cognito-id-token> --image /path/to/sky.jpg

Run 10 minutes before the demo, and again just before going on stage.
"""

import argparse
import json
import subprocess
import sys
import urllib.request
from pathlib import Path


def call_api(api_base: str, path: str, token: str, payload: dict | None = None) -> dict:
    url = api_base.rstrip("/") + path
    data = json.dumps(payload or {}).encode() if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method="POST" if payload is not None else "GET",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode()
            return {"status": response.status, "body": body[:500]}
    except Exception as exc:  # noqa: BLE001 - warm-up should report, not crash
        return {"status": "error", "body": str(exc)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Warm the demo backend before going on stage")
    parser.add_argument("--api-base", required=True, help="Deployed HTTP API base URL")
    parser.add_argument("--token", required=True, help="Cognito ID token for a demo user")
    parser.add_argument("--image", type=Path, default=None,
                        help="Sample sky JPEG for the SageMaker warm call")
    parser.add_argument("--endpoint-name", default=None,
                        help="SageMaker endpoint name (or SAGEMAKER_ENDPOINT_NAME env)")
    args = parser.parse_args()

    print("[1/3] Warming map endpoint...")
    print(call_api(args.api_base, "/map?lat=12.9763&lon=77.5929&res=6", args.token))

    if args.image:
        print("[2/3] Warming SageMaker endpoint...")
        warm_script = Path(__file__).resolve().parents[2] / "ml" / "warm_endpoint.py"
        cmd = [sys.executable, str(warm_script), "--image", str(args.image)]
        if args.endpoint_name:
            cmd += ["--endpoint-name", args.endpoint_name]
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(result.stdout[-500:] or result.stderr[-500:])
    else:
        print("[2/3] Skipped SageMaker warm-up (no --image given).")

    print("[3/3] Warming coach (Bedrock path)...")
    print(call_api(args.api_base, "/coach", args.token,
                   {"lat": 12.9763, "lon": 77.5929, "question": "Is it safe to jog now?"}))

    print("Warm-up complete.")


if __name__ == "__main__":
    main()
