# Video Transcription and YAMNet Classification Pipeline

This project implements a serverless pipeline for video transcription and audio classification using AWS services.

## Updates Made

### Lambda Function Updated

The Lambda function `VideoTranscriptionFunction` was updated to remove YAMNet preprocessing logic and delegate it to the SageMaker model.

```bash
aws lambda list-functions --region us-east-1
```

### Transcription Logic Unchanged

The AWS Transcribe integration remains exactly as it was, ensuring that video transcription continues to work as before:

```python
# Start transcription job
transcribe_response = transcribe.start_transcription_job(
    TranscriptionJobName=transcription_job_name,
    Media={'MediaFileUri': media_uri},
    MediaFormat=extension,
    LanguageCode='en-US',
    OutputBucketName=bucket_name,
    OutputKey=f"{transcription_output_key}.json"
)
```

### YAMNet Preprocessing Moved to SageMaker

The preprocessing logic that was previously in the Lambda function has been moved to the SageMaker model's `inference.py` file. The SageMaker model now:

1. Accepts raw video/audio files directly
2. Extracts audio from video files if needed
3. Converts to mono and resamples to 16kHz
4. Normalizes the audio for YAMNet processing
5. Runs the YAMNet model and returns classification results

### Deployment Commands Used

The following AWS CLI commands were used to deploy the updated solution:

```bash
# Upload the updated model to S3
aws s3 cp model.tar.gz s3://video-transcription-bucket-1747461583/models/yamnet/model.tar.gz --region us-east-1

# Delete the previous SageMaker model
aws sagemaker delete-model --model-name YamnetAudioClassificationModel --region us-east-1

# Create the updated SageMaker model
aws sagemaker create-model \
  --model-name YamnetAudioClassificationModel \
  --primary-container Image=763104351884.dkr.ecr.us-east-1.amazonaws.com/tensorflow-inference:2.11.0-cpu-py39-ubuntu20.04-sagemaker-v1.3,ModelDataUrl=s3://video-transcription-bucket-1747461583/models/yamnet/model.tar.gz \
  --execution-role-arn arn:aws:iam::637423638477:role/SageMakerYamnetRole \
  --region us-east-1

# Update the Lambda function
aws lambda update-function-code --function-name VideoTranscriptionFunction --zip-file fileb://lambda_function.zip --region us-east-1
```

## Final System Behavior

1. User uploads a video to the S3 bucket in the `input-videos/` prefix
2. The Lambda function is triggered and:
   - Starts an AWS Transcribe job for the video
   - Calls the SageMaker YAMNet model with the raw video file
3. The SageMaker model:
   - Extracts audio from the video
   - Preprocesses the audio for YAMNet
   - Runs YAMNet classification
   - Returns the results to S3
4. Both the transcription and YAMNet classification results are saved to S3

This architecture ensures that all preprocessing is handled by the SageMaker model, making the Lambda function simpler and more focused on orchestration rather than data processing.
