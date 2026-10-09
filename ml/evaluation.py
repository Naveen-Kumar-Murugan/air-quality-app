"""Evaluation: accuracy, adjacent-class accuracy, per-class precision/recall, confusion matrix."""

import argparse
import json
import sys
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader
from torchvision import datasets, models, transforms

CLASS_NAMES = [
    "Good",
    "Moderate",
    "Unhealthy for Sensitive Groups",
    "Unhealthy",
    "Very Unhealthy",
    "Hazardous",
]

ADJACENT_ACCURACY_TARGET = 0.80
ACCURACY_TARGET = 0.70


def build_eval_transforms():
    return transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
    ])


def load_model(model_path: str, device: torch.device):
    checkpoint = torch.load(model_path, map_location=device, weights_only=False)
    classes = checkpoint["classes"]
    num_classes = len(classes)

    model = models.mobilenet_v2(weights=None)
    model.classifier[1] = nn.Linear(model.last_channel, num_classes)
    model.load_state_dict(checkpoint["state_dict"])
    model.to(device)
    model.eval()
    return model, classes, checkpoint.get("metrics", {})


def compute_metrics(all_targets, all_preds, num_classes):
    total = len(all_targets)
    correct = sum(1 for t, p in zip(all_targets, all_preds) if t == p)
    adjacent = sum(1 for t, p in zip(all_targets, all_preds) if abs(t - p) <= 1)

    accuracy = correct / max(total, 1)
    adjacent_accuracy = adjacent / max(total, 1)

    confusion = [[0] * num_classes for _ in range(num_classes)]
    for t, p in zip(all_targets, all_preds):
        confusion[t][p] += 1

    per_class = {}
    for i, name in enumerate(CLASS_NAMES[:num_classes]):
        tp = confusion[i][i]
        fn = sum(confusion[i]) - tp
        fp = sum(row[i] for row in confusion) - tp

        precision = tp / max(tp + fp, 1)
        recall = tp / max(tp + fn, 1)
        support = sum(confusion[i])
        per_class[name] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "support": support,
        }

    return {
        "total_samples": total,
        "accuracy": round(accuracy, 5),
        "adjacent_accuracy": round(adjacent_accuracy, 5),
        "per_class": per_class,
        "confusion_matrix": confusion,
    }


def run_inference(model, dataloader, device):
    all_targets = []
    all_preds = []
    with torch.inference_mode():
        for inputs, targets in dataloader:
            inputs = inputs.to(device)
            logits = model(inputs)
            preds = logits.argmax(dim=1).cpu().tolist()
            all_preds.extend(preds)
            all_targets.extend(targets.tolist())
    return all_targets, all_preds


def print_report(metrics, classes, training_metrics):
    accuracy = metrics["accuracy"]
    adjacent_accuracy = metrics["adjacent_accuracy"]
    total = metrics["total_samples"]

    print("=" * 68)
    print(f"{'EVALUATION REPORT':^68}")
    print("=" * 68)
    print()

    if training_metrics:
        print(f"  Training checkpoint metrics:")
        for k, v in training_metrics.items():
            if k != "confusion_matrix":
                print(f"    {k}: {v}")
        print()

    print(f"  Validation samples: {total}")
    print(f"  Accuracy:           {accuracy:.4f}  (target: >{ACCURACY_TARGET:.0%})")
    print(f"  Adjacent accuracy:  {adjacent_accuracy:.4f}  (target: >{ADJACENT_ACCURACY_TARGET:.0%})")
    print()

    print("-" * 68)
    print(f"  {'Class':<38} {'Prec':>7} {'Recall':>7} {'Support':>8}")
    print("-" * 68)
    for name, stats in metrics["per_class"].items():
        print(f"  {name:<38} {stats['precision']:>7.4f} {stats['recall']:>7.4f} {stats['support']:>8}")
    print("-" * 68)
    print()

    print("  Confusion Matrix (rows=actual, cols=predicted):")
    header = "  {:>6}".format("") + "".join(f"  {i:>4}" for i in range(len(classes)))
    print(header)
    for i, row in enumerate(metrics["confusion_matrix"]):
        row_str = "".join(f"  {v:>4}" for v in row)
        print(f"  {i:>5}:{row_str}")
    print()
    print("  Class index mapping:")
    for i, name in enumerate(classes):
        print(f"    {i}: {name}")
    print()

    accuracy_pass = accuracy >= ACCURACY_TARGET
    adjacent_pass = adjacent_accuracy >= ADJACENT_ACCURACY_TARGET
    overall_pass = accuracy_pass and adjacent_pass

    print("=" * 68)
    print(f"  Accuracy ≥ {ACCURACY_TARGET:.0%}:          {'PASS' if accuracy_pass else 'FAIL'}")
    print(f"  Adjacent accuracy ≥ {ADJACENT_ACCURACY_TARGET:.0%}:  {'PASS' if adjacent_pass else 'FAIL'}")
    print(f"  Decision:                    {'GO' if overall_pass else 'NO-GO'}")
    print("=" * 68)

    return overall_pass


def save_results(metrics, output_path, go_decision, classes):
    results = {
        "classes": classes,
        "accuracy": metrics["accuracy"],
        "adjacent_accuracy": metrics["adjacent_accuracy"],
        "accuracy_target": ACCURACY_TARGET,
        "adjacent_accuracy_target": ADJACENT_ACCURACY_TARGET,
        "go_decision": go_decision,
        "total_samples": metrics["total_samples"],
        "per_class": metrics["per_class"],
        "confusion_matrix": metrics["confusion_matrix"],
    }
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Results saved to {output_path}")


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate AQI sky classifier model")
    parser.add_argument("--model-path", required=True, help="Path to model.pt checkpoint")
    parser.add_argument("--val-dir", required=True, help="Validation image directory (ImageFolder layout)")
    parser.add_argument("--output", default="evaluation_results.json", help="Output JSON file path")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--num-workers", type=int, default=2)
    return parser.parse_args()


def main():
    args = parse_args()

    if not Path(args.model_path).exists():
        print(f"Error: model checkpoint not found at {args.model_path}")
        sys.exit(1)
    if not Path(args.val_dir).is_dir():
        print(f"Error: validation directory not found at {args.val_dir}")
        sys.exit(1)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"  Device: {device}")

    model, classes, training_metrics = load_model(args.model_path, device)
    print(f"  Model loaded from {args.model_path}")
    print(f"  Classes ({len(classes)}): {classes}")

    eval_tfms = build_eval_transforms()
    val_ds = datasets.ImageFolder(args.val_dir, transform=eval_tfms)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, num_workers=args.num_workers)
    print(f"  Validation samples: {len(val_ds)}")

    folder_classes = val_ds.classes
    if folder_classes != classes:
        print(f"  Warning: folder classes {folder_classes} differ from checkpoint classes {classes}")

    all_targets, all_preds = run_inference(model, val_loader, device)
    metrics = compute_metrics(all_targets, all_preds, len(classes))

    go_decision = print_report(metrics, classes, training_metrics)
    save_results(metrics, args.output, go_decision, classes)

    sys.exit(0 if go_decision else 1)


if __name__ == "__main__":
    main()
