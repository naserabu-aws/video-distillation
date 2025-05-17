# Video Transcription Application

This application allows users to upload video files to AWS S3 and automatically process them using AWS Transcribe and YAMNet audio classification via SageMaker.

## Architecture

- **Frontend**: React application for uploading videos and generating presigned URLs
- **Backend**: AWS Lambda, S3, API Gateway, Transcribe, and SageMaker services

## Features

- Upload videos up to 10GB in size
- Direct upload to S3 using presigned URLs
- Real-time upload progress tracking
- Automatic transcription using AWS Transcribe
- Parallel audio classification using YAMNet via SageMaker Batch Transform
- Secure storage in a private S3 bucket

## How it Works

1. User selects a video file in the React frontend
2. Frontend requests a presigned URL from the API Gateway/Lambda backend
3. Frontend uploads the file directly to S3 using the presigned URL
4. S3 upload triggers a Lambda function
5. Lambda function starts two parallel jobs:
   - AWS Transcribe job for speech-to-text conversion
   - SageMaker Batch Transform job for YAMNet audio classification
6. Results are saved back to S3:
   - Transcription result in the `transcriptions/` folder
   - YAMNet classification result in the `yamnet-output/` folder

## Frontend Implementation

The frontend is a minimal React application that handles:

1. **Video File Selection**: Users can select video files through a standard file input
2. **API Integration**: Makes HTTP POST requests to the API Gateway endpoint to obtain presigned URLs
3. **Direct S3 Upload**: Uploads files directly to S3 using the presigned URL
4. **Upload Progress Tracking**: Shows real-time progress during the upload
5. **Status Updates**: Provides feedback on the current upload/processing status

The frontend uses:
- React for the UI components
- Axios for HTTP requests and file uploads
- No external UI libraries, keeping the implementation minimal

### API Integration Details

The frontend makes a POST request to the API endpoint with the following data:
```json
{
  "filename": "<video_file_name>",
  "contentType": "<file_mime_type>"
}
```

The Lambda function responds with:
```json
{
  "presignedUrl": "<generated_s3_presigned_url>",
  "key": "<s3_object_key>"
}
```

The frontend then performs a PUT request to the presigned URL with the file contents, which uploads the file directly to the S3 bucket.

## Running the Frontend

1. Navigate to the frontend directory:
   ```
   cd video-transcriber/frontend
   ```

2. Install dependencies:
   ```
   npm install
   ```

3. Start the development server:
   ```
   npm start
   ```

4. Open your browser to http://localhost:3000

No environment variables are required as all necessary configuration is hardcoded in `src/config.js`.

## Backend Resources

The following AWS resources have been created:

### S3 Bucket
- **Name**: video-transcription-bucket-1747461583
- **Public Access**: Blocked
- **Storage Paths**:
  - `input-videos/` - Raw video uploads
  - `transcriptions/` - Resulting transcription JSON files
  - `models/yamnet/` - YAMNet model artifacts
  - `yamnet-output/` - YAMNet classification results
- **CORS Configuration**: Enabled for `http://localhost:3000` to allow direct uploads

### IAM Resources
- **Lambda Role**: VideoTranscriptionLambdaRole
- **Lambda Policy**: VideoTranscriptionLambdaPolicy
- **Lambda Role ARN**: arn:aws:iam::637423638477:role/VideoTranscriptionLambdaRole
- **SageMaker Role**: SageMakerYamnetRole
- **SageMaker Policy**: SageMakerS3ECRAccess
- **SageMaker Role ARN**: arn:aws:iam::<account-id>:role/SageMakerYamnetRole

### Lambda Functions
- **Video Transcription Function**:
  - **Name**: VideoTranscriptionFunction
  - **ARN**: arn:aws:lambda:us-east-1:637423638477:function:VideoTranscriptionFunction
  - **Trigger**: S3 ObjectCreated events in input-videos/ prefix
  - **Runtime**: Python 3.9
  - **Handler**: transcribe_lambda_updated.lambda_handler
  - **Memory**: 5120 MB
  - **Timeout**: 900 seconds (15 minutes)

- **Presigned URL Function**:
  - **Name**: VideoPresignedUrlFunction
  - **ARN**: arn:aws:lambda:us-east-1:637423638477:function:VideoPresignedUrlFunction
  - **Runtime**: Python 3.9
  - **Handler**: presigned_url_lambda.lambda_handler
  - **Memory**: 128 MB
  - **Timeout**: 10 seconds

### SageMaker Resources
- **Model Name**: YamnetAudioClassificationModel
- **Model Data Location**: s3://video-transcription-bucket-1747461583/models/yamnet/model.tar.gz
- **Container Image**: <account-id>.dkr.ecr.<region>.amazonaws.com/yamnet-audio-classification:latest
- **Batch Transform Instance Type**: ml.g4dn.xlarge
- **Input Format**: application/octet-stream (binary video or audio file)
- **Output Format**: application/json (YAMNet classification results)

### API Gateway
- **API Name**: VideoTranscriptionAPI
- **ID**: hm24dvaawe
- **Endpoint URL**: https://hm24dvaawe.execute-api.us-east-1.amazonaws.com/prod/presigned-url
- **Supported Methods**: POST, OPTIONS
- **Stage**: prod

## Configuration

The frontend configuration is stored in `src/config.js`. Update the API_ENDPOINT if needed.

Current API endpoint: `https://hm24dvaawe.execute-api.us-east-1.amazonaws.com/prod/presigned-url`

## Processing Results

### Transcription Results
Transcription results are stored in the S3 bucket under the `transcriptions/` prefix.
The naming convention is based on the original uploaded file name with a timestamp and UUID.

Example path: `transcriptions/20250517000000-abcd1234-myvideofile.json`

### YAMNet Classification Results
YAMNet audio classification results are stored in the S3 bucket under the `yamnet-output/` prefix.
The output is a JSON file containing audio event classifications with confidence scores.

Example path: `yamnet-output/yamnet-classification-20250517000000-abcd1234-myvideofile.json`

Example output format:
```json
{
  "predictions": [
    {"class": "Speech", "score": 0.95},
    {"class": "Music", "score": 0.85},
    {"class": "Vehicle", "score": 0.45},
    {"class": "Telephone", "score": 0.32}
  ],
  "raw_scores": [...],
  "timestamp": "0.0"
}
```

## Project Structure

```
video-transcriber/
├── backend/
│   ├── lambda-trust-policy.json       # IAM trust policy for Lambda functions
│   ├── lambda-policy.json             # Original IAM policy for Lambda
│   ├── lambda-policy-updated.json     # Updated IAM policy with SageMaker permissions
│   ├── sagemaker-trust-policy.json    # IAM trust policy for SageMaker
│   ├── sagemaker-role-policy.json     # IAM policy for SageMaker role
│   ├── transcribe_lambda.py           # Original Lambda function for transcription
│   ├── transcribe_lambda_updated.py   # Updated Lambda with YAMNet integration
│   ├── prepare_yamnet_model.py        # Script to download and prepare YAMNet model
│   ├── yamnet_inference.py            # SageMaker inference script for YAMNet
│   ├── Dockerfile                     # Dockerfile for SageMaker container
│   ├── build_and_push.sh              # Script to build and push container to ECR
│   ├── create_sagemaker_model.sh      # Script to create SageMaker model
│   ├── update_lambda.sh               # Script to update Lambda function
│   ├── presigned_url_lambda.py        # Lambda for generating presigned URLs
│   ├── s3-notification-config.json    # S3 event notification configuration
│   └── cors-config.json               # CORS configuration for S3 bucket
├── frontend/
│   ├── public/                        # Static assets
│   │   └── index.html                 # Main HTML file
│   ├── package.json                   # Frontend dependencies
│   └── src/
│       ├── App.js                     # Main React component with upload functionality
│       ├── App.css                    # Minimal styling for the application
│       ├── config.js                  # Configuration with API endpoint
│       └── index.js                   # React entry point
└── README.md                          # This documentation
```

## Known Issues and Fixed Problems

- In `App.js`, line 54 has an unused variable `bucket` (ESLint warning)
- ✅ CORS configuration has been added to the S3 bucket to allow uploads from localhost
- ✅ Fixed Lambda function to sanitize output filenames for AWS Transcribe (May 17, 2025)
- ✅ Added YAMNet audio classification via SageMaker Batch Transform
- No functionality to view or download transcriptions or YAMNet results from the frontend
- No error handling for AWS Transcribe or SageMaker service failures
- Authentication not yet implemented

## Troubleshooting

### CORS Errors
If you encounter CORS errors when uploading files to S3:
1. Verify the CORS configuration on the S3 bucket allows your origin
2. Check that the presigned URL includes the correct ContentType header
3. For local development, ensure the AllowedOrigins in CORS config includes "http://localhost:3000"

### Upload Failures
If file uploads are failing:
1. Check browser console for detailed error messages
2. Verify the IAM permissions for the Lambda function that generates presigned URLs
3. Ensure the S3 bucket name in the environment variables matches the actual bucket

### Transcription or YAMNet Job Failures
1. Check CloudWatch logs for the VideoTranscriptionFunction Lambda
2. Verify that output filenames match AWS Transcribe constraints (only alphanumeric, hyphens and certain special characters allowed)
3. Ensure the Lambda role has proper permissions to start Transcribe and SageMaker jobs
4. For SageMaker failures, check CloudWatch logs for the SageMaker transform job

## AWS Service Constraints

### AWS Transcribe Filename Requirements
- Transcribe output keys must match regex pattern: `[a-zA-Z0-9-_.!*'()/&$@=;:+,? \x00-\x1F\x7F]{1,1024}$`
- Special characters outside this pattern will cause the job to fail
- The Lambda function now sanitizes filenames to ensure they meet these requirements

### YAMNet Model Information
- YAMNet is an audio event classification model
- Supports 521 audio classes from the AudioSet ontology
- Expects audio input at 16kHz, mono format
- Produces embeddings that can be used for transfer learning
- Model source: https://tfhub.dev/google/yamnet/1

## AWS CLI Commands Used

### Create SageMaker Role
```bash
aws iam create-role \
    --role-name SageMakerYamnetRole \
    --assume-role-policy-document file://sagemaker-trust-policy.json

aws iam attach-role-policy \
    --role-name SageMakerYamnetRole \
    --policy-arn arn:aws:iam::aws:policy/AmazonSageMakerFullAccess

aws iam put-role-policy \
    --role-name SageMakerYamnetRole \
    --policy-name SageMakerS3ECRAccess \
    --policy-document file://sagemaker-role-policy.json
```

### Create ECR Repository and Push Docker Image
```bash
aws ecr create-repository --repository-name yamnet-audio-classification

aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <account-id>.dkr.ecr.<region>.amazonaws.com

docker build -t yamnet-audio-classification -f Dockerfile .

docker tag yamnet-audio-classification <account-id>.dkr.ecr.<region>.amazonaws.com/yamnet-audio-classification:latest

docker push <account-id>.dkr.ecr.<region>.amazonaws.com/yamnet-audio-classification:latest
```

### Create SageMaker Model
```bash
aws sagemaker create-model \
    --model-name YamnetAudioClassificationModel \
    --primary-container '{"Image": "<account-id>.dkr.ecr.<region>.amazonaws.com/yamnet-audio-classification:latest", "ModelDataUrl": "s3://video-transcription-bucket-1747461583/models/yamnet/model.tar.gz"}' \
    --execution-role-arn arn:aws:iam::<account-id>:role/SageMakerYamnetRole
```

### Update Lambda Function
```bash
aws iam put-role-policy \
    --role-name VideoTranscriptionLambdaRole \
    --policy-name VideoTranscriptionLambdaPolicy \
    --policy-document file://lambda-policy-updated.json

aws lambda update-function-code \
    --function-name VideoTranscriptionFunction \
    --zip-file fileb://updated_lambda.zip

aws lambda update-function-configuration \
    --function-name VideoTranscriptionFunction \
    --handler transcribe_lambda_updated.lambda_handler
```

## Potential Next Steps

1. Add authentication using Amazon Cognito
2. Create a viewer component in the frontend for transcription and YAMNet results
3. Add support for transcription in multiple languages
4. Implement job status monitoring
5. Add automated tests for both frontend and backend components
6. Fix the unused variable warning in `App.js`
7. Add video playback with synchronized transcription and audio event markers
8. Implement CloudWatch alarms for monitoring and alerts
9. Extract audio from video files before running YAMNet classification for better results

## Workspace Setup Notes

This project was set up with the following AWS CLI commands:

1. Create S3 bucket: `aws s3api create-bucket`
2. Create IAM roles and policies: `aws iam create-role`, `aws iam create-policy`
3. Deploy Lambda functions: `aws lambda create-function`
4. Configure S3 event notifications: `aws s3api put-bucket-notification-configuration`
5. Set up API Gateway: `aws apigateway create-rest-api`, `aws apigateway create-deployment`
6. Configure CORS for S3: `aws s3api put-bucket-cors`

All backend components were deployed using direct AWS CLI commands, not using frameworks like CloudFormation or CDK. 