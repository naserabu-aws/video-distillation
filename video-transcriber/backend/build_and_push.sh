#!/bin/bash

# Get AWS account ID
account=$(aws sts get-caller-identity --query Account --output text)

# Get AWS region
region=$(aws configure get region)
region=${region:-us-east-1}

# Full name of the ECR repository
fullname="${account}.dkr.ecr.${region}.amazonaws.com/yamnet-audio-classification:latest"

# Create the ECR repository if it doesn't exist
aws ecr describe-repositories --repository-names "yamnet-audio-classification" > /dev/null 2>&1
if [ $? -ne 0 ]
then
    aws ecr create-repository --repository-name "yamnet-audio-classification" > /dev/null
fi

# Log in to ECR
aws ecr get-login-password --region ${region} | docker login --username AWS --password-stdin "${account}.dkr.ecr.${region}.amazonaws.com"

# Build the Docker image
cd $(dirname "$0")
docker build -t "yamnet-audio-classification" -f Dockerfile .

# Tag the image
docker tag "yamnet-audio-classification" ${fullname}

# Push the image to ECR
docker push ${fullname}

echo "Docker image pushed to ${fullname}" 