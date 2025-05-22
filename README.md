# Video Highlight Dashboard

A web application that automatically generates highlight videos from uploaded content using AWS services and Claude 3.5.

## Features

- Upload videos to AWS S3
- Automatic transcription and highlight detection
- AI-powered highlight clip generation using Claude 3.5
- Dashboard to view and manage videos and their highlights
- Auto-refreshing status updates

## Architecture

### Frontend

- React-based web application
- Direct API calls to AWS API Gateway
- Thumbnail previews with hover-to-play functionality
- Status indicators for highlight generation

### Backend

- AWS Lambda functions for video processing
- DynamoDB for tracking video-highlight relationships
- S3 for storing videos, transcripts, and highlights
- Claude 3.5 for intelligent highlight clip generation

## Lambda Functions

1. **PresignedUrlFunction**: Generates presigned URLs for uploading videos to S3
2. **ListVideosFunction**: Lists recent videos and their highlight status
3. **HighlightVideoCutterFunction**: Processes highlights JSON and cuts video segments

## DynamoDB Schema

The `VideoHighlights` table tracks the relationship between input videos and their highlight videos:

- `video_id` (Primary Key): Unique identifier for the video
- `input_video_key`: S3 key for the input video
- `highlight_video_key`: S3 key for the generated highlight video
- `highlight_json_key`: S3 key for the highlights JSON file
- `timestamp`: ISO 8601 timestamp of when the record was created/updated
- `status`: Status of the highlight generation process (generating/completed)

## Deployment

### Backend Deployment

1. Create the DynamoDB table:
   ```
   ./create_dynamodb_table.sh
   ```

2. Update the IAM policy for Lambda functions:
   ```
   ./update_lambda_policy.sh
   ```

3. Deploy the Lambda functions:
   ```
   ./deploy_highlight_cutter_lambda.sh
   ./deploy_list_videos_lambda.sh
   ```

4. Set up the proxy server environment:
   ```
   cp .env.example .env
   ```
   Then edit the `.env` file with your API Gateway endpoint.

5. Install proxy server dependencies:
   ```
   npm install
   ```

6. Start the proxy server:
   ```
   npm start
   ```

### Frontend Deployment

1. Navigate to the frontend directory:
   ```
   cd frontend
   ```

2. Set up environment variables:
   ```
   cp .env.example .env
   ```
   Then edit the `.env` file with your AWS credentials and configuration.

3. Install dependencies:
   ```
   npm install
   ```

4. Start the development server:
   ```
   npm start
   ```

### Running the Complete Application

To run both the proxy server and frontend together:

1. Make sure you've set up both backend and frontend environment variables.

2. Run the start script:
   ```
   ./start-app.sh
   ```

This script will start both the proxy server and the frontend application, and will properly handle shutdown of both processes when you press Ctrl+C.

## Usage

1. Open the web application
2. Upload a video using the drag-and-drop interface
3. Wait for the video to be processed
4. View the generated highlight video when ready

## Workflow

1. User uploads a video to S3 via the frontend
2. Video is transcribed and analyzed for highlights
3. Highlights JSON is generated and uploaded to S3
4. HighlightVideoCutterFunction is triggered by the S3 upload
5. Claude 3.5 generates FFmpeg commands for highlight clips
6. FFmpeg extracts highlight clips and concatenates them
7. The final highlight video is uploaded to S3
8. DynamoDB is updated with the highlight video information
9. Frontend displays the highlight video status and link

## GitHub Setup

This project is configured for GitHub with the following considerations:

1. **Environment Variables**: Sensitive credentials are stored in `.env` files which are excluded from Git via `.gitignore`. Use the provided `.env.example` files as templates.

2. **Large Files**: Binary files, videos, and large datasets are excluded from Git tracking.

3. **Logs and Temporary Files**: All logs and temporary runtime files are excluded.

To set up a new environment after cloning:

1. Copy the example environment files:
   ```
   cp .env.example .env
   cp frontend/.env.example frontend/.env
   ```

2. Update the environment variables with your own credentials.

3. Follow the deployment instructions above to set up the backend and frontend.
