#!/bin/bash

# Get AWS account ID and region
account=$(aws sts get-caller-identity --query Account --output text)
region=$(aws configure get region)
region=${region:-us-east-1}

# Set variables
bucket_name="video-transcription-bucket-1747461583"
model_name="YamnetAudioClassificationModel"
role_name="SageMakerYamnetRole"
role_arn="arn:aws:iam::${account}:role/${role_name}"
ecr_image="${account}.dkr.ecr.${region}.amazonaws.com/yamnet-audio-classification:latest"
model_data_url="s3://${bucket_name}/models/yamnet/model.tar.gz"

# Create SageMaker IAM role if it doesn't exist
aws iam get-role --role-name ${role_name} > /dev/null 2>&1
if [ $? -ne 0 ]
then
    echo "Creating SageMaker role ${role_name}..."
    aws iam create-role \
        --role-name ${role_name} \
        --assume-role-policy-document file://sagemaker-trust-policy.json

    # Attach AmazonSageMakerFullAccess managed policy
    aws iam attach-role-policy \
        --role-name ${role_name} \
        --policy-arn arn:aws:iam::aws:policy/AmazonSageMakerFullAccess

    # Create and attach custom policy
    aws iam put-role-policy \
        --role-name ${role_name} \
        --policy-name SageMakerS3ECRAccess \
        --policy-document file://sagemaker-role-policy.json
    
    # Wait for role to propagate
    echo "Waiting for role to propagate..."
    sleep 10
fi

# Create SageMaker model
echo "Creating SageMaker model ${model_name}..."
aws sagemaker create-model \
    --model-name ${model_name} \
    --primary-container "{\"Image\": \"${ecr_image}\", \"ModelDataUrl\": \"${model_data_url}\"}" \
    --execution-role-arn ${role_arn}

echo "SageMaker model ${model_name} created" 