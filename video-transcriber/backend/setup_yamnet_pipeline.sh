#!/bin/bash

set -e

echo "Setting up YAMNet audio classification pipeline..."

# Install required Python packages
echo "Installing required Python packages..."
pip install tensorflow tensorflow-hub librosa soundfile numpy boto3

# Download and prepare YAMNet model
echo "Downloading and preparing YAMNet model..."
python prepare_yamnet_model.py

# Build and push Docker image to ECR
echo "Building and pushing Docker image to ECR..."
chmod +x build_and_push.sh
./build_and_push.sh

# Create SageMaker model
echo "Creating SageMaker model..."
chmod +x create_sagemaker_model.sh
./create_sagemaker_model.sh

# Update Lambda function
echo "Updating Lambda function..."
chmod +x update_lambda.sh
./update_lambda.sh

echo "YAMNet audio classification pipeline setup complete!"
echo "The system will now process uploaded videos with both AWS Transcribe for transcription and YAMNet for audio classification." 