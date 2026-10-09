#!/bin/bash

# Test local ML setup before running SageMaker training

set -e

echo "Testing local ML setup for Air Quality app"
echo "=========================================="

# ------------------------------------------------------------
# 1. Check Python environment
# ------------------------------------------------------------

echo -e "\n1. Checking Python environment..."

PYTHON="python3"

echo "Python:"
$PYTHON --version

echo "Python executable:"
$PYTHON -c "import sys; print(sys.executable)"

echo "Pip:"
$PYTHON -m pip --version


# ------------------------------------------------------------
# 2. Check SSL certificates
# ------------------------------------------------------------

echo -e "\n2. Checking Python SSL certificates..."

$PYTHON -c "
import ssl

print('SSL OpenSSL version:', ssl.OPENSSL_VERSION)
print('CA certificate file:', ssl.get_default_verify_paths().cafile)

if not ssl.get_default_verify_paths().cafile:
    raise SystemExit('ERROR: Python does not have a CA certificate configured.')
"

echo "Testing HTTPS connection..."

$PYTHON -c "
import urllib.request

url = 'https://download.pytorch.org/models/'

try:
    response = urllib.request.urlopen(url, timeout=10)
    print('HTTPS connection successful:', response.status)

except Exception as e:
    error = str(e)

    if 'CERTIFICATE_VERIFY_FAILED' in error:
        print()
        print('ERROR: Python SSL certificates are not configured correctly.')
        print()
        print('Run this once on macOS:')
        print('  open \"/Applications/Python 3.13/Install Certificates.command\"')
        print()
        raise SystemExit(1)

    print('HTTPS server responded:', error)
"


# ------------------------------------------------------------
# 3. Install requirements
# ------------------------------------------------------------

echo -e "\n3. Installing requirements..."

$PYTHON -m pip install -r ml/requirements.txt


# ------------------------------------------------------------
# 4. Check PyTorch installation
# ------------------------------------------------------------

echo -e "\n4. Checking PyTorch installation..."

$PYTHON -c "
import torch

print('PyTorch:', torch.__version__)
print('CUDA available:', torch.cuda.is_available())
"

$PYTHON -c "
import torchvision

print('Torchvision:', torchvision.__version__)
"


# ------------------------------------------------------------
# 5. Test MobileNetV2 pretrained weights
# ------------------------------------------------------------

echo -e "\n5. Testing MobileNetV2 pretrained weights..."

$PYTHON -c "
from torchvision import models

weights = models.MobileNet_V2_Weights.DEFAULT

print('MobileNetV2 weights URL:')
print(weights.url)

print()
print('Loading MobileNetV2...')

model = models.mobilenet_v2(weights=weights)

print('MobileNetV2 pretrained weights loaded successfully.')
"


# ------------------------------------------------------------
# 6. Download small test dataset from S3
# ------------------------------------------------------------

echo -e "\n6. Preparing small test dataset from S3..."

mkdir -p ml/data/test_train
mkdir -p ml/data/test_val


# ------------------------------------------------------------
# Dataset configuration
# ------------------------------------------------------------

CLASSES=(
    "a_Good"
    "b_Moderate"
    "c_Unhealthy_for_Sensitive_Groups"
    "d_Unhealthy"
    "e_Very_Unhealthy"
    "f_Severe"
)

TRAIN_LIMIT=20
VAL_LIMIT=10


# ------------------------------------------------------------
# Download dataset only when needed
# ------------------------------------------------------------

for class in "${CLASSES[@]}"; do

    echo
    echo "Processing class: $class..."

    # Create class directories
    mkdir -p "ml/data/test_train/$class"
    mkdir -p "ml/data/test_val/$class"


    # ========================================================
    # TRAIN DATA
    # ========================================================

    TRAIN_DIR="ml/data/test_train/$class"

    TRAIN_COUNT=$(find "$TRAIN_DIR" -maxdepth 1 -type f -name "*.jpg" | wc -l | tr -d ' ')

    if [ "$TRAIN_COUNT" -ge "$TRAIN_LIMIT" ]; then

        echo "  Train: already have $TRAIN_COUNT images. Skipping S3 download."

    else

        NEEDED=$((TRAIN_LIMIT - TRAIN_COUNT))

        echo "  Train: have $TRAIN_COUNT images, need $NEEDED more."

        aws s3api list-objects-v2 \
            --bucket "aq-models-dev" \
            --prefix "datasets/sky-aqi/v1/train/$class/" \
            --query "Contents[?ends_with(Key, '.jpg')].Key" \
            --output text 2>/dev/null |
            tr '\t' '\n' |
            while read -r file; do

                # Skip empty lines / None
                if [ -z "$file" ] || [ "$file" = "None" ]; then
                    continue
                fi

                # Stop once enough images have been downloaded
                CURRENT_COUNT=$(find "$TRAIN_DIR" -maxdepth 1 -type f -name "*.jpg" | wc -l | tr -d ' ')

                if [ "$CURRENT_COUNT" -ge "$TRAIN_LIMIT" ]; then
                    break
                fi

                echo "    -> Copying: $(basename "$file")"

                aws s3 cp \
                    "s3://aq-models-dev/$file" \
                    "$TRAIN_DIR/" \
                    --quiet

            done

    fi


    # ========================================================
    # VALIDATION DATA
    # ========================================================

    VAL_DIR="ml/data/test_val/$class"

    VAL_COUNT=$(find "$VAL_DIR" -maxdepth 1 -type f -name "*.jpg" | wc -l | tr -d ' ')

    if [ "$VAL_COUNT" -ge "$VAL_LIMIT" ]; then

        echo "  Val:   already have $VAL_COUNT images. Skipping S3 download."

    else

        NEEDED=$((VAL_LIMIT - VAL_COUNT))

        echo "  Val:   have $VAL_COUNT images, need $NEEDED more."

        aws s3api list-objects-v2 \
            --bucket "aq-models-dev" \
            --prefix "datasets/sky-aqi/v1/val/$class/" \
            --query "Contents[?ends_with(Key, '.jpg')].Key" \
            --output text 2>/dev/null |
            tr '\t' '\n' |
            while read -r file; do

                # Skip empty lines / None
                if [ -z "$file" ] || [ "$file" = "None" ]; then
                    continue
                fi

                # Stop once enough images have been downloaded
                CURRENT_COUNT=$(find "$VAL_DIR" -maxdepth 1 -type f -name "*.jpg" | wc -l | tr -d ' ')

                if [ "$CURRENT_COUNT" -ge "$VAL_LIMIT" ]; then
                    break
                fi

                echo "    -> Copying: $(basename "$file")"

                aws s3 cp \
                    "s3://aq-models-dev/$file" \
                    "$VAL_DIR/" \
                    --quiet

            done

    fi

done


# ------------------------------------------------------------
# 7. Dataset summary
# ------------------------------------------------------------

echo -e "\n7. Dataset summary:"

TRAIN_COUNT=$(find ml/data/test_train -type f -name "*.jpg" | wc -l | tr -d ' ')
VAL_COUNT=$(find ml/data/test_val -type f -name "*.jpg" | wc -l | tr -d ' ')

echo "  Train images: $TRAIN_COUNT"
echo "  Val images:   $VAL_COUNT"


# ------------------------------------------------------------
# 8. Test training script
# ------------------------------------------------------------

echo -e "\n8. Testing training script..."

$PYTHON ml/train.py \
    --train-dir ml/data/test_train \
    --val-dir ml/data/test_val \
    --epochs 1 \
    --batch-size 4 \
    --lr 0.001 \
    --unfreeze-epoch 999


# ------------------------------------------------------------
# 9. Success
# ------------------------------------------------------------

echo
echo "=========================================="
echo "✅ All tests passed!"
echo "=========================================="

echo
echo "Local ML setup is working."

echo
echo "Next steps:"
echo "  1. Run full dataset analysis:"
echo "     python3 ml/dataset_stats.py"

echo
echo "  2. Get SageMaker execution role ARN"

echo
echo "  3. Launch full training:"
echo "     export SAGEMAKER_EXECUTION_ROLE_ARN='arn:aws:iam::...'"

echo
echo "     export ML_DATASET_S3_URI='s3://aq-models-dev/datasets/sky-aqi/v1'"

echo
echo "     python3 -c 'from sagemaker.pytorch import PyTorch; ...'"