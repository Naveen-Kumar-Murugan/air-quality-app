"""Create or update the AQI SageMaker serverless endpoint without invoking deployment by default."""

import argparse
import json
import os


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-data", required=True, help="S3 URI for model.tar.gz")
    parser.add_argument("--role-arn", default=os.environ.get("SAGEMAKER_EXECUTION_ROLE_ARN"))
    parser.add_argument("--endpoint-name", default=os.environ.get("SAGEMAKER_ENDPOINT_NAME", "aq-sky-classifier"))
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "ap-south-1"))
    parser.add_argument("--memory-mb", type=int, default=4096)
    parser.add_argument("--max-concurrency", type=int, default=5)
    parser.add_argument("--apply", action="store_true", help="Deploy the endpoint. Omit to print the reproducible deployment plan.")
    return parser.parse_args()


def deployment_plan(args):
    if not args.role_arn:
        raise ValueError("--role-arn or SAGEMAKER_EXECUTION_ROLE_ARN is required")
    return {
        "endpoint_name": args.endpoint_name,
        "model_data": args.model_data,
        "role_arn": args.role_arn,
        "region": args.region,
        "framework_version": "2.1",
        "py_version": "py310",
        "memory_mb": args.memory_mb,
        "max_concurrency": args.max_concurrency,
    }


def main():
    args = parse_args()
    plan = deployment_plan(args)
    print(json.dumps(plan, indent=2, sort_keys=True))
    if not args.apply:
        print("Deployment not started. Re-run with --apply to create/update the endpoint.")
        return

    from sagemaker.pytorch import PyTorchModel
    from sagemaker.serverless import ServerlessInferenceConfig

    model = PyTorchModel(
        model_data=args.model_data,
        role=args.role_arn,
        entry_point="inference.py",
        source_dir=os.path.dirname(__file__),
        framework_version="2.1",
        py_version="py310",
    )
    model.deploy(
        endpoint_name=args.endpoint_name,
        serverless_inference_config=ServerlessInferenceConfig(
            memory_size_in_mb=args.memory_mb,
            max_concurrency=args.max_concurrency,
        ),
    )


if __name__ == "__main__":
    main()
