#!/bin/bash
# Test local ML setup before running SageMaker training

set -e

echo "Testing local ML setup for Air Quality app"
echo "=========================================="

# Check Python environment
echo -e "\n1. Checking Python environment..."
python --version
pip --version

# Install requirements
echo -e "\n2. Installing requirements..."
pip install -r requirements.txt

# Check PyTorch installation
echo -e "\n3. Checking PyTorch installation..."
python -c "import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA available: {torch.cuda.is_available()}')"

# Download small test dataset from S3
echo -e "\n4. Downloading small test dataset from S3..."
mkdir -p data/test_train data/test_val

# Download 20 images per class for testing
for class in "a_Good" "b_Moderate" "c_Unhealthy_for_Sensitive_Groups" "d_Unhealthy" "e_Very_Unhealthy" "f_Severe"; do
    echo "  Downloading $class..."
    
    # Create class directories
    mkdir -p "data/test_train/$class" "data/test_val/$class"
    
    # Download a few images to train
    aws s3 sync "s3://aq-models-dev/datasets/sky-aqi/v1/train/$class/" "data/test_train/$class/" \
        --exclude "*" \
        --include "*.jpg" \
        --max-items 20 \
        --quiet || echo "  Warning: No train images for $class"
    
    # Download a few images to val  
    aws s3 sync "s3://aq-models-dev/datasets/sky-aqi/v1/val/$class/" "data/test_val/$class/" \
        --exclude "*" \
        --include "*.jpg" \
        --max-items 10 \
        --quiet || echo "  Warning: No val images for $class"
done

# Count downloaded images
echo -e "\n5. Dataset summary:"
echo "  Train images:" $(find data/test_train -name "*.jpg" | wc -l)
echo "  Val images:" $(find data/test_val -name "*.jpg" | wc -l)

# Test training script with tiny config
echo -e "\n6. Testing training script (dry run)..."
python train.py \
    --train-dir data/test_train \
    --val-dir data/test_val \
    --epochs 1 \
    --batch-size 4 \
    --lr 0.001 \
    --unfreeze-epoch 999  # Don't unfreeze for test run

if [ $? -eq 0 ]; then
    echo -e "\n✅ All tests passed! Local setup is working."
    echo -e "\nNext steps:"
    echo "  1. Run full dataset analysis: python ml/dataset_stats.py"
    echo "  2. Get SageMaker execution role ARN"
    echo "  3. Launch full training:"
    echo "     export SAGEMAKER_EXECUTION_ROLE_ARN='arn:aws:iam::...'"
    echo "     export ML_DATASET_S3_URI='s3://aq-models-dev/datasets/sky-aqi/v1'"
    echo "     python -c 'from sagemaker.pytorch import PyTorch; ...'"
else
    echo -e "\n❌ Training test failed. Check the error above."
    exit 1
fi