"""Local/SageMaker training entrypoint for the six-class AQI sky classifier."""

import argparse
import json
import os
import random
from pathlib import Path

CLASS_NAMES = [
    "Good",
    "Moderate",
    "Unhealthy for Sensitive Groups",
    "Unhealthy",
    "Very Unhealthy",
    "Hazardous",
]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=int(os.environ.get("SM_HP_EPOCHS", 8)))
    parser.add_argument("--batch-size", type=int, default=int(os.environ.get("SM_HP_BATCH_SIZE", 32)))
    parser.add_argument("--lr", type=float, default=float(os.environ.get("SM_HP_LR", 3e-4)))
    parser.add_argument("--unfreeze-epoch", type=int, default=int(os.environ.get("SM_HP_UNFREEZE_EPOCH", 3)))
    parser.add_argument("--seed", type=int, default=int(os.environ.get("SM_HP_SEED", 42)))
    parser.add_argument("--train-dir", default=os.environ.get("SM_CHANNEL_TRAIN", os.environ.get("ML_TRAIN_DIR", "data/train")))
    parser.add_argument("--val-dir", default=os.environ.get("SM_CHANNEL_VAL", os.environ.get("ML_VAL_DIR", "data/val")))
    parser.add_argument("--dataset-s3-uri", default=os.environ.get("ML_DATASET_S3_URI"))
    parser.add_argument("--model-dir", default=os.environ.get("SM_MODEL_DIR", "model"))
    return parser.parse_args()


def main():
    args = parse_args()
    if args.dataset_s3_uri:
        print(json.dumps({"dataset_s3_uri": args.dataset_s3_uri, "note": "SageMaker channels must reference the prepared train and val prefixes."}), flush=True)
    random.seed(args.seed)

    import torch
    from torch import nn
    from torch.utils.data import DataLoader
    from torchvision import datasets, models, transforms

    torch.manual_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    train_tfms = transforms.Compose([
        transforms.RandomResizedCrop(224, scale=(0.85, 1.0)),
        transforms.RandomHorizontalFlip(),
        transforms.ColorJitter(brightness=0.15, contrast=0.1),
        transforms.ToTensor(),
        transforms.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
    ])
    eval_tfms = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
    ])

    train_ds = datasets.ImageFolder(args.train_dir, transform=train_tfms)
    val_ds = datasets.ImageFolder(args.val_dir, transform=eval_tfms)
    if len(train_ds.classes) != len(CLASS_NAMES):
        raise ValueError(f"Expected {len(CLASS_NAMES)} class folders, found {len(train_ds.classes)}")

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, num_workers=2)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, num_workers=2)

    weights = models.MobileNet_V2_Weights.DEFAULT
    model = models.mobilenet_v2(weights=weights)
    model.classifier[1] = nn.Linear(model.last_channel, len(CLASS_NAMES))
    model.to(device)

    for param in model.features.parameters():
        param.requires_grad = False

    class_counts = [0] * len(train_ds.classes)
    for _, label in train_ds.samples:
        class_counts[label] += 1
    class_weights = torch.tensor([sum(class_counts) / max(count, 1) for count in class_counts], dtype=torch.float32, device=device)
    criterion = nn.CrossEntropyLoss(weight=class_weights)
    optimizer = torch.optim.AdamW((p for p in model.parameters() if p.requires_grad), lr=args.lr)

    best_adjacent = -1.0
    Path(args.model_dir).mkdir(parents=True, exist_ok=True)

    for epoch in range(args.epochs):
        if epoch == args.unfreeze_epoch:
            for param in model.features.parameters():
                param.requires_grad = True
            optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr * 0.1)

        train_loss = train_one_epoch(model, train_loader, criterion, optimizer, device)
        metrics = evaluate(model, val_loader, criterion, device)
        metrics.update({"epoch": epoch + 1, "train_loss": train_loss})
        print(json.dumps(metrics), flush=True)

        if metrics["adjacent_accuracy"] >= best_adjacent:
            best_adjacent = metrics["adjacent_accuracy"]
            torch.save({"state_dict": model.state_dict(), "classes": train_ds.classes, "metrics": metrics}, Path(args.model_dir) / "model.pt")


def train_one_epoch(model, loader, criterion, optimizer, device):
    model.train()
    total_loss = 0.0
    total = 0
    for inputs, targets in loader:
        inputs = inputs.to(device)
        targets = targets.to(device)
        optimizer.zero_grad(set_to_none=True)
        loss = criterion(model(inputs), targets)
        loss.backward()
        optimizer.step()
        total_loss += loss.item() * inputs.size(0)
        total += inputs.size(0)
    return round(total_loss / max(total, 1), 5)


def evaluate(model, loader, criterion, device):
    import torch

    model.eval()
    total_loss = 0.0
    total = 0
    correct = 0
    adjacent = 0
    confusion = [[0 for _ in CLASS_NAMES] for _ in CLASS_NAMES]
    with torch.inference_mode():
        for inputs, targets in loader:
            inputs = inputs.to(device)
            targets = targets.to(device)
            logits = model(inputs)
            loss = criterion(logits, targets)
            preds = logits.argmax(dim=1)
            total_loss += loss.item() * inputs.size(0)
            total += inputs.size(0)
            correct += (preds == targets).sum().item()
            adjacent += (torch.abs(preds - targets) <= 1).sum().item()
            for target, pred in zip(targets.cpu().tolist(), preds.cpu().tolist()):
                confusion[target][pred] += 1
    return {
        "val_loss": round(total_loss / max(total, 1), 5),
        "accuracy": round(correct / max(total, 1), 5),
        "adjacent_accuracy": round(adjacent / max(total, 1), 5),
        "confusion_matrix": confusion,
    }


if __name__ == "__main__":
    main()
