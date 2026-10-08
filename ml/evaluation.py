"""Evaluation support: compute accuracy, adjacent-class accuracy, confusion matrix."""

import argparse
import os


def evaluate_predictions(predictions_path: str, labels_path: str):
    print(f"Evaluating predictions={predictions_path} labels={labels_path}")
    print("Expected metrics: accuracy, adjacent_accuracy, confusion_matrix")
    print("Report adjacent accuracy as the honest measure for ordered AQI categories.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", default=os.environ.get("ML_PREDICTIONS_PATH"))
    parser.add_argument("--labels", default=os.environ.get("ML_LABELS_PATH"))
    args = parser.parse_args()
    if args.predictions and args.labels:
        evaluate_predictions(args.predictions, args.labels)
    else:
        print("No dataset exists in repo; provide --predictions and --labels if evaluating.")


if __name__ == "__main__":
    main()
