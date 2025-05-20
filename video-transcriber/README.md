# Video Transcription Application

This application allows users to upload video files to AWS S3 and automatically transcribe them using AWS Transcribe.

## Architecture

- **Frontend**: React application for uploading videos and generating presigned URLs
- **Backend**: AWS Lambda, S3, API Gateway, and Transcribe services

## Features

- Upload videos up to 10GB in size
- Direct upload to S3 using presigned URLs
- Real-time upload progress tracking
- Automatic transcription using AWS Transcribe
- Secure storage in a private S3 bucket

## How it Works

1. User selects a video file in the React frontend
2. Frontend requests a presigned URL from the API Gateway/Lambda backend
3. Frontend uploads the file directly to S3 using the presigned URL
4. S3 upload triggers a Lambda function
5. Lambda function starts an AWS Transcribe job
6. Transcription result is saved back to S3 in the transcriptions/ folder

## Running the Frontend

1. Navigate to the frontend directory:
   ```
   cd frontend
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

## Backend Resources

The following AWS resources have been created:

### S3 Bucket
- **Name**: video-transcription-bucket-1747461583
- **Public Access**: Blocked
- **Storage Paths**:
  - `input-videos/` - Raw video uploads
  - `transcriptions/` - Resulting transcription JSON files
- **CORS Configuration**: Enabled for `http://localhost:3000` to allow direct uploads

### IAM Resources
- **Role**: VideoTranscriptionLambdaRole
- **Policy**: VideoTranscriptionLambdaPolicy
- **ARN**: arn:aws:iam::637423638477:role/VideoTranscriptionLambdaRole

### Lambda Functions
- **Video Transcription Function**:
  - **Name**: VideoTranscriptionFunction
  - **ARN**: arn:aws:lambda:us-east-1:637423638477:function:VideoTranscriptionFunction
  - **Trigger**: S3 ObjectCreated events in input-videos/ prefix
  - **Runtime**: Python 3.9
  - **Handler**: transcribe_lambda.lambda_handler
  - **Memory**: 5120 MB
  - **Timeout**: 900 seconds (15 minutes)

- **Presigned URL Function**:
  - **Name**: VideoPresignedUrlFunction
  - **ARN**: arn:aws:lambda:us-east-1:637423638477:function:VideoPresignedUrlFunction
  - **Runtime**: Python 3.9
  - **Handler**: presigned_url_lambda.lambda_handler
  - **Memory**: 128 MB
  - **Timeout**: 10 seconds

### API Gateway
- **API Name**: VideoTranscriptionAPI
- **ID**: hm24dvaawe
- **Endpoint URL**: https://hm24dvaawe.execute-api.us-east-1.amazonaws.com/prod/presigned-url
- **Supported Methods**: POST, OPTIONS
- **Stage**: prod

## Configuration

The frontend configuration is stored in `src/config.js`. Update the API_ENDPOINT if needed.

Current API endpoint: `https://hm24dvaawe.execute-api.us-east-1.amazonaws.com/prod/presigned-url`

## Transcription Results

Transcription results are stored in the S3 bucket under the `transcriptions/` prefix.
The naming convention is based on the original uploaded file name with a timestamp and UUID.

Example path: `transcriptions/20250517000000-abcd1234-myvideofile.json`

## Project Structure

```
video-transcriber/
├── backend/
│   ├── lambda-trust-policy.json       # IAM trust policy for Lambda functions
│   ├── lambda-policy.json             # IAM policy with S3 & Transcribe permissions
│   ├── transcribe_lambda.py           # Lambda triggered by S3 uploads
│   ├── presigned_url_lambda.py        # Lambda for generating presigned URLs
│   ├── s3-notification-config.json    # S3 event notification configuration
│   └── cors-config.json               # CORS configuration for S3 bucket
├── frontend/
│   ├── public/                        # Static assets
│   └── src/
│       ├── App.js                     # Main React component
│       ├── App.css                    # Styles for the application
│       ├── config.js                  # Configuration including API endpoints
│       └── ...                        # Other React files
└── README.md                          # This documentation
```

## Known Issues and Fixed Problems

- In `App.js`, line 54 has an unused variable `bucket` (ESLint warning)
- ✅ CORS configuration has been added to the S3 bucket to allow uploads from localhost
- ✅ Fixed Lambda function to sanitize output filenames for AWS Transcribe (May 17, 2025)
- No functionality to view or download transcriptions from the frontend
- No error handling for AWS Transcribe service failures
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

### Transcription Job Failures
If transcription jobs are failing:
1. Check CloudWatch logs for the VideoTranscriptionFunction Lambda
2. Verify that output filenames match AWS Transcribe constraints (only alphanumeric, hyphens and certain special characters allowed)
3. Ensure the Lambda role has proper permissions to start Transcribe jobs

## AWS Service Constraints

### AWS Transcribe Filename Requirements
- Transcribe output keys must match regex pattern: `[a-zA-Z0-9-_.!*'()/&$@=;:+,? \x00-\x1F\x7F]{1,1024}$`
- Special characters outside this pattern will cause the job to fail
- The Lambda function now sanitizes filenames to ensure they meet these requirements

## Potential Next Steps

1. Add authentication using Amazon Cognito
2. Create a transcription viewer component in the frontend
3. Add support for transcription in multiple languages
4. Implement transcription job status monitoring
5. Add automated tests for both frontend and backend components
6. Fix the unused variable warning in `App.js`
7. Add video playback with synchronized transcription
8. Implement CloudWatch alarms for monitoring and alerts

## Workspace Setup Notes

This project was set up with the following AWS CLI commands:

1. Create S3 bucket: `aws s3api create-bucket`
2. Create IAM roles and policies: `aws iam create-role`, `aws iam create-policy`
3. Deploy Lambda functions: `aws lambda create-function`
4. Configure S3 event notifications: `aws s3api put-bucket-notification-configuration`
5. Set up API Gateway: `aws apigateway create-rest-api`, `aws apigateway create-deployment`
6. Configure CORS for S3: `aws s3api put-bucket-cors`

All backend components were deployed using direct AWS CLI commands, not using frameworks like CloudFormation or CDK. 