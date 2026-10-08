import argparse
import sys
import subprocess

STEPS = {
    "stats": ("ml.dataset_stats", []),
    "train": ("ml.launch_training", []),
    "evaluate": ("ml.evaluation", []),
    "deploy": ("ml.deploy", []),
    "warm": ("ml.warm_endpoint", []),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", default="all", help="Comma-separated steps or all")
    parser.add_argument("--role-arn", default=None)
    parser.add_argument("--model-data", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    args = parser.parse_args()

    if args.steps == "all":
        selected = list(STEPS.keys())
    else:
        selected = [s.strip() for s in args.steps.split(",") if s.strip()]

    failed = False
    for step in selected:
        if step not in STEPS:
            print(f"[FAIL] Unknown step: {step}")
            failed = True
            if not args.continue_on_error:
                break
            continue

        module_name, _ = STEPS[step]
        cmd = [sys.executable, "-m", module_name]

        if step == "train" and args.role_arn:
            cmd += ["--role-arn", args.role_arn]
        if step == "train" and args.dry_run:
            cmd += ["--dry-run"]
        if step == "deploy":
            if args.model_data:
                cmd += ["--model-data", args.model_data]
            if args.role_arn:
                cmd += ["--role-arn", args.role_arn]

        print(f"\n{'='*60}")
        print(f"STEP: {step}")
        print(f"COMMAND: {' '.join(cmd)}")
        print(f"{'='*60}")

        if args.dry_run:
            print("DRY-RUN: skipped")
            continue

        result = subprocess.run(cmd)
        if result.returncode == 0:
            print(f"[PASS] {step}")
        else:
            print(f"[FAIL] {step} (exit {result.returncode})")
            failed = True
            if not args.continue_on_error:
                break

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
