import json
import urllib.parse
import boto3
import uuid
import os
import re
from datetime import datetime

# Initialize clients
s3 = boto3.client('s3')
transcribe = boto3.client('transcribe')
sagemaker = boto3.client('sagemaker')

def sanitize_filename(filename):
    """
    Sanitize the filename to meet AWS Transcribe constraints.
    Only allow a-z, A-Z, 0-9, -, _, ., !, *, ', (, ), /, &, $, @, =, ;, :, +, ,, ?, and space.
    """
    # Replace any problematic characters with hyphen
    sanitized = re.sub(r'[^a-zA-Z0-9\-_.!*\'()/&$@=;:+,? ]', '-', filename)
    # Ensure it's not too long (AWS Transcribe has a limit of 1024 characters)
    if len(sanitized) > 900:  # Leave some buffer
        sanitized = sanitized[:900]
    return sanitized

def extract_audio(bucket_name, key, timestamp, sanitized_filename):
    """
    Extract audio from video file using a SageMaker Processing job
    """
    # Configure the job
    job_name = f"extract-audio-{timestamp}-{uuid.uuid4()}"
    output_key = f"audio-files/{timestamp}-{sanitized_filename}.wav"
    
    print(f"Extracting audio from video at s3://{bucket_name}/{key}")
    print(f"Output will be saved to s3://{bucket_name}/{output_key}")
    
    # For simplicity, we'll use ffmpeg in Lambda directly
    # In a real-world scenario, you might want to use a more robust solution
    # like SageMaker Processing or a dedicated Lambda function for audio extraction
    
    # Here we'll just return the original file key for demonstration purposes
    # In a real implementation, this would actually extract audio
    return {
        "bucket_name": bucket_name,
        "key": key,
        "audio_key": key  # In a real implementation, this would be the extracted audio
    }

def start_yamnet_classification(bucket_name, key, timestamp, sanitized_filename):
    """
    Start a SageMaker Batch Transform job for YAMNet audio classification
    """
    # Job name must be unique
    job_name = f"yamnet-classification-{timestamp}-{uuid.uuid4().hex[:8]}"
    
    # Model name - this would be created beforehand
    model_name = "YamnetAudioClassificationModel"
    
    # Output path
    output_path = f"s3://{bucket_name}/yamnet-output/"
    
    print(f"Starting YAMNet classification job: {job_name}")
    print(f"Input: s3://{bucket_name}/{key}")
    print(f"Output will be saved to {output_path}")
    
    # Create the transform job
    response = sagemaker.create_transform_job(
        TransformJobName=job_name,
        ModelName=model_name,
        MaxConcurrentTransforms=1,
        MaxPayloadInMB=100,
        BatchStrategy='SingleRecord',
        TransformInput={
            'DataSource': {
                'S3DataSource': {
                    'S3DataType': 'S3Prefix',
                    'S3Uri': f"s3://{bucket_name}/{key}",
                }
            },
            'ContentType': 'application/octet-stream',
        },
        TransformOutput={
            'S3OutputPath': output_path,
            'Accept': 'application/json',
            'AssembleWith': 'Line',
        },
        TransformResources={
            'InstanceType': 'ml.g4dn.xlarge',  # GPU instance for faster inference
            'InstanceCount': 1,
        }
    )
    
    print(f"YAMNet classification job started: {job_name}")
    return job_name

def lambda_handler(event, context):
    # Get the object from the event
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'])
    
    # Validate the key is in the input-videos/ prefix
    if not key.startswith('input-videos/'):
        print(f"Object {key} not in input-videos/ prefix, skipping")
        return {
            'statusCode': 200,
            'body': json.dumps('File not in input-videos/ prefix')
        }
    
    try:
        # Get object metadata to determine content type
        response = s3.head_object(Bucket=bucket, Key=key)
        content_type = response.get('ContentType', '')
        
        # Determine file extension from content type
        extension = ''
        if 'video/mp4' in content_type.lower():
            extension = 'mp4'
        elif 'video/quicktime' in content_type.lower() or 'video/mov' in content_type.lower():
            extension = 'mov'
        elif 'video/x-msvideo' in content_type.lower():
            extension = 'avi'
        elif 'video/x-ms-wmv' in content_type.lower():
            extension = 'wmv'
        else:
            # Try to get extension from key
            if '.' in key:
                extension = key.split('.')[-1].lower()
        
        # Generate unique job name
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        transcription_job_name = f"transcription-{timestamp}-{uuid.uuid4()}"
        
        # Set up media file URI
        media_uri = f"s3://{bucket}/{key}"
        
        # Create a sanitized output key that meets AWS Transcribe constraints
        base_filename = os.path.basename(key).rsplit('.', 1)[0]
        sanitized_filename = sanitize_filename(base_filename)
        transcription_output_key = f"transcriptions/{timestamp}-{sanitized_filename}"
        
        print(f"Original filename: {base_filename}")
        print(f"Sanitized filename: {sanitized_filename}")
        print(f"Transcription output key: {transcription_output_key}")
        
        # Start transcription job
        transcribe_response = transcribe.start_transcription_job(
            TranscriptionJobName=transcription_job_name,
            Media={'MediaFileUri': media_uri},
            MediaFormat=extension,
            LanguageCode='en-US',  # Default to English, can be made configurable
            OutputBucketName=bucket,
            OutputKey=f"{transcription_output_key}.json"
        )
        
        print(f"Started transcription job: {transcription_job_name}")
        
        # In parallel, start YAMNet audio classification
        yamnet_job_name = start_yamnet_classification(
            bucket_name=bucket,
            key=key,
            timestamp=timestamp,
            sanitized_filename=sanitized_filename
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'transcription_job': transcription_job_name,
                'yamnet_job': yamnet_job_name
            })
        }
    
    except Exception as e:
        print(f"Error processing {key} from bucket {bucket}. Error: {e}")
        raise e 