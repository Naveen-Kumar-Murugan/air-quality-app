#!/usr/bin/env python3
"""Reset demo-seeded data so rehearsals start from a clean slate.

Deletes the items written by seed_bangalore.py (stations, demo geocells and
historical scans) and optionally re-seeds. Supports DynamoDB Local and AWS.

Usage:
    python reset_demo_data.py --local --reseed
    python reset_demo_data.py --reseed --stations-table StationsTable
"""

import argparse
import os
import sys

import boto3


def get_dynamodb_client(local: bool = False):
    if local:
        return boto3.resource("dynamodb", endpoint_url="http://localhost:8000",
                              region_name="ap-south-1")
    return boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "ap-south-1"))


def delete_all(table, label: str, pk_prefix: str | None = None) -> int:
    count = 0
    kwargs: dict = {}
    while True:
        response = table.scan(**kwargs) if not kwargs else table.scan(**kwargs)
        items = response.get("Items", [])
        with table.batch_writer() as batch:
            for item in items:
                if pk_prefix and not str(item.get("pk", "")).startswith(pk_prefix):
                    continue
                batch.delete_item(Key={"pk": item["pk"], "sk": item["sk"]})
                count += 1
        kwargs["ExclusiveStartKey"] = response.get("LastEvaluatedKey")
        if not kwargs["ExclusiveStartKey"]:
            kwargs = {}
            break
        if not response.get("LastEvaluatedKey"):
            break
    print(f"  deleted {count} item(s) from {label}")
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset demo-seeded DynamoDB data")
    parser.add_argument("--local", action="store_true",
                        help="Use DynamoDB Local (http://localhost:8000)")
    parser.add_argument("--reseed", action="store_true",
                        help="Re-run seed_bangalore.py after clearing")
    parser.add_argument("--stations-table", default="StationsTable")
    parser.add_argument("--geocells-table", default="GeoCellsTable")
    parser.add_argument("--scans-table", default="ScansTable")
    parser.add_argument("--skip-scans", action="store_true",
                        help="Keep scan history (only clear stations/geocells)")
    args = parser.parse_args()

    dynamodb = get_dynamodb_client(local=args.local)

    print("Clearing demo-seeded data...")
    delete_all(dynamodb.Table(args.stations_table), args.stations_table)
    delete_all(dynamodb.Table(args.geocells_table), args.geocells_table)
    if not args.skip_scans:
        delete_all(dynamodb.Table(args.scans_table), args.scans_table,
                   pk_prefix="U#test-user-bangalore")

    if args.reseed:
        import subprocess
        seed_path = os.path.join(os.path.dirname(__file__), "seed_bangalore.py")
        cmd = [sys.executable, seed_path,
               "--stations-table", args.stations_table,
               "--geocells-table", args.geocells_table,
               "--scans-table", args.scans_table]
        if args.local:
            cmd.append("--local")
        print("Re-seeding...")
        subprocess.run(cmd, check=True)

    print("Reset complete.")


if __name__ == "__main__":
    main()
