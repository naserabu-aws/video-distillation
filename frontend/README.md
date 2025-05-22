# Video Highlights Generator Frontend

A React application for uploading videos and viewing generated highlight clips.

## Features

- Upload MP4 video files
- Show upload progress
- Display processing status
- View generated highlight videos

## Setup

1. Install dependencies:
   ```
   npm install
   ```

2. Create a `.env` file with the following variables:
   ```
   REACT_APP_API_ENDPOINT=https://z1hp4fkcbd.execute-api.us-east-1.amazonaws.com/prod/presigned-url
   REACT_APP_S3_BUCKET=video-transcription-bucket-1747461583
   ```

3. Start the development server:
   ```
   npm start
   ```

## How It Works

1. User uploads an MP4 video file
2. The app gets a presigned URL from the API Gateway
3. The video is uploaded directly to S3
4. The app polls for the generated highlight video
5. Once available, the highlight video is displayed

## Backend Integration

This frontend integrates with AWS services:
- API Gateway for getting presigned URLs
- S3 for storing videos and retrieving highlight clips
- Lambda functions (indirectly) for video processing

## Technologies Used

- React
- Fetch API for network requests
- Environment variables for configuration
