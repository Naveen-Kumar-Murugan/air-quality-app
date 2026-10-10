#!/usr/bin/env python3
"""Set 7-day CloudWatch log retention on all stack Lambda log groups.

Lambda auto-creates its log group on first invoke, so retention is applied
out-of-band rather than via CloudFormation (managing LogGroups in the SAM
template caused EarlyValidation and AlreadyExists deploy failures).

Usage:
    python set_log_retention.py [--stack-name air-quality-app-stack] [--days 7]
"""

import argparse

import boto3


def main() -> None:
    parser = argparse.ArgumentParser(description="Set Lambda log group retention")
    parser.add_argument("--stack-name", default="air-quality-app-stack")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--region", default="ap-south-1")
    args = parser.parse_args()

    cf = boto3.client("cloudformation", region_name=args.region)
    logs = boto3.client("logs", region_name=args.region)

    resources = cf.describe_stack_resources(StackName=args.stack_name)["StackResources"]
    functions = [r["PhysicalResourceId"] for r in resources
                 if r["ResourceType"] == "AWS::Lambda::Function"]

    for function_name in sorted(functions):
        log_group = f"/aws/lambda/{function_name}"
        try:
            logs.put_retention_policy(logGroupName=log_group, retentionInDays=args.days)
            print(f"  {log_group}: retention set to {args.days} days")
        except logs.exceptions.ResourceNotFoundException:
            print(f"  {log_group}: no log group yet (function never invoked), skipped")


if __name__ == "__main__":
    main()
