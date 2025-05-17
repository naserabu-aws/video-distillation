
import json
import urllib.parse
import boto3
import uuid
import os
import re
import tempfile
import subprocess
import numpy as np
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
    sanitized = re.sub(r"[^a-zA-Z0-9\-_.!*'()/&$@=;:+,? ]", '-', filename)
    # Ensure it's not too long (AWS Transcribe has a limit of 1024 characters)
    if len(sanitized) > 900:  # Leave some buffer
        sanitized = sanitized[:900]
    return sanitized

def check_video_format(bucket_name, key):
    """
    Check if the video is in a supported format.
    Returns the file extension.
    """
    # Get object metadata to determine content type
    response = s3.head_object(Bucket=bucket_name, Key=key)
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
    
    return extension

def start_transcription_job(bucket_name, key, timestamp, sanitized_filename, extension):
    """
    Start an AWS Transcribe job for the video
    """
    # Generate unique job name
    transcription_job_name = f"transcription-{timestamp}-{uuid.uuid4()}"
    
    # Set up media file URI
    media_uri = f"s3://{bucket_name}/{key}"
    
    # Create a sanitized output key
    transcription_output_key = f"transcriptions/{timestamp}-{sanitized_filename}"
    
    print(f"Starting transcription job: {transcription_job_name}")
    print(f"Input: {media_uri}")
    print(f"Output: s3://{bucket_name}/{transcription_output_key}.json")
    
    # Start transcription job
    transcribe_response = transcribe.start_transcription_job(
        TranscriptionJobName=transcription_job_name,
        Media={'MediaFileUri': media_uri},
        MediaFormat=extension,
        LanguageCode='en-US',  # Default to English, can be made configurable
        OutputBucketName=bucket_name,
        OutputKey=f"{transcription_output_key}.json"
    )
    
    return transcription_job_name

def preprocess_video_for_yamnet(bucket_name, key, timestamp, sanitized_filename):
    """
    Process video for YAMNet by:
    1. Extracting audio 
    2. Resampling to 16kHz mono
    3. Converting to NumPy array
    4. Saving as .npy file in S3
    """
    # Define S3 keys
    npy_key = f"yamnet/input/{timestamp}-{sanitized_filename}.npy"
    
    # Set up a temporary directory for processing
    with tempfile.TemporaryDirectory() as temp_dir:
        # Local paths for processing
        local_video = os.path.join(temp_dir, os.path.basename(key))
        local_audio = os.path.join(temp_dir, "audio.wav")
        local_npy = os.path.join(temp_dir, "input.npy")
        
        print(f"Downloading video from s3://{bucket_name}/{key}")
        s3.download_file(bucket_name, key, local_video)
        
        # Layer installs ffmpeg in /opt/bin/ffmpeg
        ffmpeg_binary = '/opt/bin/ffmpeg'
        if not os.path.exists(ffmpeg_binary):
            print("FFmpeg not found at /opt/bin/ffmpeg, trying other locations...")
            ffmpeg_binary = '/var/task/bin/ffmpeg'
            if not os.path.exists(ffmpeg_binary):
                ffmpeg_binary = 'ffmpeg'  # Try system path as last resort
        
        # Extract audio using ffmpeg
        print("Extracting audio from video...")
        try:
            subprocess.check_call([
                ffmpeg_binary, "-i", local_video, 
                "-ac", "1", "-ar", "16000", 
                "-y", local_audio
            ])
        except Exception as e:
            print(f"Error using ffmpeg: {e}")
            raise Exception(f"Failed to extract audio from video: {e}")
        
        # Convert audio to numpy array
        try:
            print("Loading audio with scipy...")
            sr, y = wavfile.read(local_audio)
            # Convert to float32 in range [-1, 1]
            y = y.astype(np.float32)
            if y.max() > 1.0:
                y = y / 32768.0  # Assuming 16-bit audio
            np.save(local_npy, y)
            
            # Upload the .npy file to S3
            print(f"Uploading .npy file to s3://{bucket_name}/{npy_key}")
            s3.upload_file(local_npy, bucket_name, npy_key)
            
            return npy_key
        except Exception as e:
            print(f"Error converting audio to numpy array: {e}")
            raise e

def start_yamnet_classification(bucket_name, npy_key, timestamp, sanitized_filename):
    """
    Start a SageMaker Batch Transform job for YAMNet audio classification
    using preprocessed .npy input
    """
    # Job name must be unique
    job_name = f"yamnet-classification-{timestamp}-{uuid.uuid4().hex[:8]}"
    
    # Model name
    model_name = "YamnetAudioClassificationModel"
    
    # Output path
    output_path = f"s3://{bucket_name}/yamnet-output/"
    
    print(f"Starting YAMNet classification job: {job_name}")
    print(f"Input: s3://{bucket_name}/{npy_key}")
    print(f"Output will be saved to {output_path}")
    
    # Create the transform job with proper content type for .npy files
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
                    'S3Uri': f"s3://{bucket_name}/{npy_key}",
                }
            },
            'ContentType': 'application/x-npy',  # Proper content type for NumPy arrays
            'SplitType': 'None',  # Process the entire file as one input
        },
        TransformOutput={
            'S3OutputPath': output_path,
            'Accept': 'application/json',
            'AssembleWith': 'Line',
        },
        TransformResources={
            'InstanceType': 'ml.m5.large',  # CPU is sufficient for YAMNet inference
            'InstanceCount': 1,
        }
    )
    
    print(f"YAMNet classification job started: {job_name}")
    return job_name

def lambda_handler(event, context):
    try:
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
            # Generate timestamp for job names
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            
            # Get the file extension and check format
            extension = check_video_format(bucket, key)
            
            # Create a sanitized filename
            base_filename = os.path.basename(key).rsplit('.', 1)[0]
            sanitized_filename = sanitize_filename(base_filename)
            
            print(f"Original filename: {base_filename}")
            print(f"Sanitized filename: {sanitized_filename}")
            
            # Start transcription job
            transcription_job_name = start_transcription_job(
                bucket_name=bucket,
                key=key,
                timestamp=timestamp,
                sanitized_filename=sanitized_filename,
                extension=extension
            )
            
            # Process video for YAMNet
            try:
                npy_key = preprocess_video_for_yamnet(
                    bucket_name=bucket,
                    key=key,
                    timestamp=timestamp,
                    sanitized_filename=sanitized_filename
                )
                
                # Start YAMNet classification with the preprocessed .npy file
                yamnet_job_name = start_yamnet_classification(
                    bucket_name=bucket,
                    npy_key=npy_key,
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
            except Exception as yamnet_error:
                print(f"Error in YAMNet processing: {yamnet_error}")
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'transcription_job': transcription_job_name,
                        'yamnet_error': str(yamnet_error)
                    })
                }
            
        except Exception as processing_error:
            print(f"Error processing {key} from bucket {bucket}. Error: {processing_error}")
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'error': str(processing_error)
                })
            }
    except Exception as event_error:
        print(f"Error parsing event: {event_error}")
        print(f"Event: {json.dumps(event)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Failed to process event',
                'details': str(event_error)
            })
        }
