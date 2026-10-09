"""Analyze dataset statistics from S3 to inform training decisions."""

import argparse
import json
import os
from collections import defaultdict


def main():
    parser = argparse.ArgumentParser(description="Analyze AQI dataset statistics from S3")
    parser.add_argument(
        "--bucket",
        default="aq-models-dev",
        help="S3 bucket containing the dataset"
    )
    parser.add_argument(
        "--prefix",
        default="datasets/sky-aqi/v1",
        help="S3 prefix for the dataset"
    )
    parser.add_argument(
        "--output",
        default="dataset_stats.json",
        help="Output file for statistics"
    )
    args = parser.parse_args()

    try:
        import boto3
    except ImportError:
        print("Error: boto3 not installed. Run: pip install boto3")
        return 1

    s3 = boto3.client("s3")
    
    stats = {
        "bucket": args.bucket,
        "prefix": args.prefix,
        "splits": {},
        "classes": [
            "a_Good",
            "b_Moderate", 
            "c_Unhealthy_for_Sensitive_Groups",
            "d_Unhealthy",
            "e_Very_Unhealthy",
            "f_Severe"
        ]
    }

    print(f"Analyzing dataset: s3://{args.bucket}/{args.prefix}")
    print("=" * 60)

    for split in ["train", "val"]:
        print(f"\n{split.upper()} Split:")
        split_stats = {
            "total_images": 0,
            "classes": {},
            "sizes_mb": []
        }

        for class_name in stats["classes"]:
            prefix = f"{args.prefix}/{split}/{class_name}/"
            print(f"  Scanning {class_name}...", end=" ")
            
            paginator = s3.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=args.bucket, Prefix=prefix)
            
            count = 0
            sizes = []
            
            for page in pages:
                if "Contents" in page:
                    for obj in page["Contents"]:
                        if obj["Key"].lower().endswith((".jpg", ".jpeg", ".png")):
                            count += 1
                            sizes.append(obj["Size"])
                            split_stats["sizes_mb"].append(obj["Size"] / (1024 * 1024))
            
            split_stats["classes"][class_name] = {
                "count": count,
                "avg_size_kb": round(sum(sizes) / len(sizes) / 1024, 2) if sizes else 0
            }
            split_stats["total_images"] += count
            print(f"{count} images")

        stats["splits"][split] = split_stats

        # Print summary
        print(f"\n  Total {split} images: {split_stats['total_images']}")
        
        # Class balance
        if split_stats["total_images"] > 0:
            print(f"\n  Class distribution:")
            for class_name, class_info in split_stats["classes"].items():
                percentage = (class_info["count"] / split_stats["total_images"]) * 100
                print(f"    {class_name:40s}: {class_info['count']:5d} ({percentage:5.1f}%)")

    # Overall statistics
    print("\n" + "=" * 60)
    print("OVERALL STATISTICS:")
    total_train = stats["splits"]["train"]["total_images"]
    total_val = stats["splits"]["val"]["total_images"]
    total = total_train + total_val
    
    print(f"  Total images: {total}")
    print(f"  Train/Val split: {total_train}/{total_val} ({total_train/total*100:.1f}%/{total_val/total*100:.1f}%)")
    
    # Check for class imbalance
    print("\n  Class imbalance analysis:")
    train_counts = [info["count"] for info in stats["splits"]["train"]["classes"].values()]
    val_counts = [info["count"] for info in stats["splits"]["val"]["classes"].values()]
    
    if train_counts:
        train_min, train_max = min(train_counts), max(train_counts)
        val_min, val_max = min(val_counts), max(val_counts)
        
        train_imbalance = train_max / train_min if train_min > 0 else float("inf")
        val_imbalance = val_max / val_min if val_min > 0 else float("inf")
        
        print(f"    Train imbalance ratio: {train_imbalance:.2f}x (min={train_min}, max={train_max})")
        print(f"    Val imbalance ratio: {val_imbalance:.2f}x (min={val_min}, max={val_max})")
        
        if train_imbalance > 5:
            print("    ⚠️  WARNING: Significant class imbalance detected. Consider:")
            print("       - Using class weights (already implemented in train.py)")
            print("       - Oversampling minority classes")
            print("       - Data augmentation for minority classes")
    
    # Storage estimate
    total_size_mb = sum(stats["splits"]["train"]["sizes_mb"]) + sum(stats["splits"]["val"]["sizes_mb"])
    print(f"\n  Total dataset size: {total_size_mb:.1f} MB ({total_size_mb/1024:.2f} GB)")
    
    # Save to file
    with open(args.output, "w") as f:
        json.dump(stats, f, indent=2)
    
    print(f"\n✓ Statistics saved to: {args.output}")
    print("\nRecommendations:")
    print("  1. Review class distribution for significant imbalance")
    print("  2. Check if train/val split ratio is appropriate (typical: 80/20)")
    print("  3. Verify no data leakage between train/val (location/session based split)")
    print(f"  4. Ready to train? Set S3_TRAIN_URI=s3://{args.bucket}/{args.prefix}/train")
    print(f"     and S3_VAL_URI=s3://{args.bucket}/{args.prefix}/val")

    return 0


if __name__ == "__main__":
    exit(main())
