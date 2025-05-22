#!/bin/bash

# Fix for the "No module named 'lambda_function'" error

# 1. Copy the transcribe_lambda.py to lambda_function.py
cp transcribe_lambda.py lambda_function.py

# 2. Create a new ZIP package with the lambda_function.py
zip -j new_lambda_function.zip lambda_function.py

# 3. Update the Lambda function code
aws lambda update-function-code \
  --function-name VideoTranscriptionFunction \
  --zip-file fileb://new_lambda_function.zip

# 4. Update the Lambda function configuration to use the correct handler
aws lambda update-function-configuration \
  --function-name VideoTranscriptionFunction \
  --handler lambda_function.lambda_handler

echo "Deployment complete. The Lambda function should now work properly." 