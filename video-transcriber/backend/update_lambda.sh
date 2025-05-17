#!/bin/bash

# Set variables
lambda_function_name="VideoTranscriptionFunction"
role_name="VideoTranscriptionLambdaRole"

# Get AWS account ID
account=$(aws sts get-caller-identity --query Account --output text)
role_arn="arn:aws:iam::${account}:role/${role_name}"

# Update the Lambda function IAM policy
echo "Updating IAM policy for Lambda function..."
aws iam put-role-policy \
    --role-name ${role_name} \
    --policy-name VideoTranscriptionLambdaPolicy \
    --policy-document file://lambda-policy-updated.json

# Zip the updated Lambda function
echo "Packaging Lambda function..."
zip -j updated_lambda.zip transcribe_lambda_updated.py

# Update the Lambda function
echo "Updating Lambda function ${lambda_function_name}..."
aws lambda update-function-code \
    --function-name ${lambda_function_name} \
    --zip-file fileb://updated_lambda.zip

# Update Lambda handler to point to the new file
aws lambda update-function-configuration \
    --function-name ${lambda_function_name} \
    --handler transcribe_lambda_updated.lambda_handler

# Clean up
rm updated_lambda.zip

echo "Lambda function ${lambda_function_name} updated" 