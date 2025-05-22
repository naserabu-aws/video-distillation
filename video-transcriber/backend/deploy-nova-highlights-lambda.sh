#!/bin/bash

# Set variables
LAMBDA_NAME="NovaHighlightsLambda"
ROLE_NAME="VideoTranscriptionLambdaRole" # Reuse the existing role
BUCKET_NAME="video-transcription-bucket-1747461583"
REGION="us-east-1"

# Zip the Lambda function
echo "Zipping Lambda function code..."
zip nova_highlights_lambda.zip nova_highlights_lambda.py

# Create or update the Lambda function
echo "Deploying Lambda function..."
aws lambda create-function \
    --function-name $LAMBDA_NAME \
    --runtime python3.9 \
    --handler nova_highlights_lambda.lambda_handler \
    --memory-size 512 \
    --timeout 300 \
    --role arn:aws:iam::637423638477:role/$ROLE_NAME \
    --zip-file fileb://nova_highlights_lambda.zip \
    --environment "Variables={VIDEO_BUCKET=$BUCKET_NAME,TRANSCRIPT_BUCKET=$BUCKET_NAME,HIGHLIGHTS_BUCKET=$BUCKET_NAME,MODEL_ID=amazon.nova-pro-v1:0}" \
    --region $REGION

# In case the function already exists, update the code
if [ $? -ne 0 ]; then
    echo "Function already exists. Updating code..."
    aws lambda update-function-code \
        --function-name $LAMBDA_NAME \
        --zip-file fileb://nova_highlights_lambda.zip \
        --region $REGION
        
    # Update function configuration
    echo "Updating function configuration..."
    aws lambda update-function-configuration \
        --function-name $LAMBDA_NAME \
        --handler nova_highlights_lambda.lambda_handler \
        --memory-size 512 \
        --timeout 300 \
        --environment "Variables={VIDEO_BUCKET=$BUCKET_NAME,TRANSCRIPT_BUCKET=$BUCKET_NAME,HIGHLIGHTS_BUCKET=$BUCKET_NAME,MODEL_ID=amazon.nova-pro-v1:0}" \
        --region $REGION
fi

# Add permissions for S3 to invoke the Lambda function
echo "Adding permissions for S3 to invoke Lambda..."
aws lambda add-permission \
    --function-name $LAMBDA_NAME \
    --statement-id s3-invoke \
    --action lambda:InvokeFunction \
    --principal s3.amazonaws.com \
    --source-arn arn:aws:s3:::$BUCKET_NAME \
    --source-account $(aws sts get-caller-identity --query Account --output text) \
    --region $REGION

# Configure S3 event notification
echo "Configuring S3 event notification..."
aws s3api put-bucket-notification-configuration \
    --bucket $BUCKET_NAME \
    --notification-configuration file://combined-s3-notification-config.json \
    --region $REGION

echo "Deployment complete." 