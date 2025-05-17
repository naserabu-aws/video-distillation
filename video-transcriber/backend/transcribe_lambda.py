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
        job_name = f"transcription-{timestamp}-{uuid.uuid4()}"
        
        # Set up media file URI
        media_uri = f"s3://{bucket}/{key}"
        
        # Create a sanitized output key that meets AWS Transcribe constraints
        base_filename = os.path.basename(key).rsplit('.', 1)[0]
        sanitized_filename = sanitize_filename(base_filename)
        output_key = f"transcriptions/{timestamp}-{sanitized_filename}"
        
        print(f"Original filename: {base_filename}")
        print(f"Sanitized filename: {sanitized_filename}")
        print(f"Output key: {output_key}")
        
        # Start transcription job
        transcribe_response = transcribe.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={'MediaFileUri': media_uri},
            MediaFormat=extension,
            LanguageCode='en-US',  # Default to English, can be made configurable
            OutputBucketName=bucket,
            OutputKey=f"{output_key}.json"
        )
        
        print(f"Started transcription job: {job_name}")
        return {
            'statusCode': 200,
            'body': json.dumps(f"Started transcription job: {job_name}")
        }
    
    except Exception as e:
        print(f"Error processing {key} from bucket {bucket}. Error: {e}")
        raise e 