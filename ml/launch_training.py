"""Launch a SageMaker training job for the AQI sky classifier."""

import argparse
import json
import os
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--role-arn", default=os.environ.get("SAGEMAKER_EXECUTION_ROLE_ARN"))
    parser.add_argument("--dataset-s3-uri", default="s3://aq-models-dev/datasets/sky-aqi/v1")
    parser.add_argument("--instance-type", default="ml.g4dn.xlarge")
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--unfreeze-epoch", type=int, default=3)
    parser.add_argument("--output-s3-uri", default="s3://aq-models-dev/models/")
    parser.add_argument("--max-run", type=int, default=3600)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.role_arn:
        print("ERROR: --role-arn or SAGEMAKER_EXECUTION_ROLE_ARN required")
        sys.exit(1)

    train_path = args.dataset_s3_uri.rstrip("/") + "/train"
    val_path = args.dataset_s3_uri.rstrip("/") + "/val"

    hyperparameters = {
        "epochs": args.epochs,
        "batch-size": args.batch_size,
        "lr": args.lr,
        "unfreeze-epoch": args.unfreeze_epoch,
    }

    config = {
        "role": args.role_arn,
        "dataset": args.dataset_s3_uri,
        "instance_type": args.instance_type,
        "hyperparameters": hyperparameters,
        "output": args.output_s3_uri,
        "train_channel": train_path,
        "val_channel": val_path,
        "max_run": args.max_run,
    }

    if args.dry_run:
        print("DRY RUN")
        print(json.dumps(config, indent=2))
        return

    import boto3
    from sagemaker.pytorch import PyTorch
    from sagemaker import Session

    session = Session(boto_session=boto3.Session(region_name="ap-south-1"))

    estimator = PyTorch(
        entry_point="train.py",
        source_dir=os.path.join(os.path.dirname(__file__)),
        role=args.role_arn,
        instance_count=1,
        instance_type=args.instance_type,
        framework_version="2.1.0",
        py_version="py310",
        hyperparameters=hyperparameters,
        output_path=args.output_s3_uri,
        max_run=args.max_run,
        sagemaker_session=session,
    )

    estimator.fit({"train": train_path, "val": val_path}, wait=True)
    print("Model artifact:", estimator.model_data)


if __name__ == "__main__":
    main()
