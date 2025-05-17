# Video Transcription and YAMNet Classification Pipeline

This project implements a serverless pipeline for video transcription and audio classification using AWS services.

## Updates Made

### Fixed SageMaker Model Deployment Error

Fixed the `ValueError: no SavedModel bundles found!` error by repackaging the model.tar.gz file with the correct versioned directory structure. TensorFlow Serving requires the model to be placed inside a subfolder named like a version (e.g., `1/`), or it will fail to load the model.

#### Original model.tar.gz structure (incorrect):
```
model/
model/saved_model.pb
model/variables/
model/inference.py
model/class_labels.json
model/assets/
```

#### Fixed model.tar.gz structure (correct):
```
model/
model/1/
model/1/saved_model.pb
model/1/variables/
model/1/inference.py
model/1/class_labels.json
model/1/assets/
```

### Transcription Logic Unchanged

The AWS Transcribe integration remains exactly as it was, ensuring that video transcription continues to work as before. No changes were made to the Lambda function's transcription logic.

### No Fallback to Lambda for Preprocessing

The inference logic in the SageMaker model was not altered. The model continues to handle all preprocessing steps as before:

1. Accepts raw video/audio files directly
2. Extracts audio from video files if needed
3. Converts to mono and resamples to 16kHz
4. Normalizes the audio for YAMNet processing
5. Runs the YAMNet model and returns classification results

The only change was to the model's directory structure to comply with TensorFlow Serving requirements.

### Deployment Commands Used

The following AWS CLI commands were used to fix the model deployment:

```bash
# Verify the existing model archive structure
tar -tf model.tar.gz

# Extract the model to a temporary directory
mkdir -p model_extract && tar -xzf model.tar.gz -C model_extract

# Create the correct directory structure with versioned directory
mkdir -p model_fix/model/1

# Copy the model files to the versioned directory
cp -r model_extract/model/* model_fix/model/1/

# Create the new model archive with the correct structure
cd model_fix && tar -czf ../new_model.tar.gz model

# Verify the new model archive structure
tar -tf new_model.tar.gz

# Upload the fixed model to S3
aws s3 cp new_model.tar.gz s3://video-transcription-bucket-1747461583/models/yamnet/model.tar.gz --region us-east-1

# Delete the previous SageMaker model
aws sagemaker delete-model --model-name YamnetAudioClassificationModel --region us-east-1

# Create a new SageMaker model with the fixed model archive
aws sagemaker create-model --model-name YamnetAudioClassificationModel --primary-container "{\"Image\":\"763104351884.dkr.ecr.us-east-1.amazonaws.com/tensorflow-inference:2.11.0-cpu-py39-ubuntu20.04-sagemaker-v1.3\",\"ModelDataUrl\":\"s3://video-transcription-bucket-1747461583/models/yamnet/model.tar.gz\"}" --execution-role-arn arn:aws:iam::637423638477:role/SageMakerYamnetRole --region us-east-1
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

This architecture ensures that all preprocessing is handled by the SageMaker model, making the Lambda function simpler and more focused on orchestration rather than data processing. The Lambda function was identified using AWS CLI, not by inspecting code files.
