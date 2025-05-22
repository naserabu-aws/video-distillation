import json
import boto3
import os
import uuid
import urllib.parse
from datetime import datetime
import logging
import re
import time
import random
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize clients
s3 = boto3.client('s3')
bedrock_runtime = boto3.client('bedrock-runtime')

# Environment variables
VIDEO_BUCKET = os.environ.get('VIDEO_BUCKET', 'video-transcription-bucket-1747461583')
TRANSCRIPT_BUCKET = os.environ.get('TRANSCRIPT_BUCKET', 'video-transcription-bucket-1747461583')
HIGHLIGHTS_BUCKET = os.environ.get('HIGHLIGHTS_BUCKET', 'video-transcription-bucket-1747461583')
MODEL_ID = os.environ.get('MODEL_ID', 'amazon.nova-pro-v1:0')  # Nova Pro supports on-demand invocation
INFERENCE_PROFILE_ARN = os.environ.get('INFERENCE_PROFILE_ARN', '')  # Only needed for Nova Premier, not Pro
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')

# Retry configuration
MAX_RETRIES = 5
INITIAL_BACKOFF = 1  # seconds
# Increase backoff multiplier to slow down retries more aggressively
BACKOFF_MULTIPLIER = 3  # Was previously defaulting to 2

def invoke_with_retry(model_id, payload):
    """
    Invoke Bedrock model with exponential backoff retry logic for throttling
    
    Parameters:
    - model_id: The ID of the Bedrock model to invoke
    - payload: The JSON payload to send to the model
    
    Returns:
    - The model response
    """
    retry_count = 0
    backoff = INITIAL_BACKOFF
    
    while True:
        try:
            logger.info(f"Invoking model attempt {retry_count + 1}/{MAX_RETRIES + 1}")
            
            # If using Nova Premier and an inference profile ARN is provided, use it
            invoke_params = {
                'modelId': model_id,
                'contentType': "application/json",
                'accept': "application/json",
                'body': payload
            }
            
            if model_id == 'amazon.nova-premier-v1:0' and INFERENCE_PROFILE_ARN:
                logger.info(f"Using inference profile: {INFERENCE_PROFILE_ARN}")
                invoke_params['inferenceProfileArn'] = INFERENCE_PROFILE_ARN
                
            response = bedrock_runtime.invoke_model(**invoke_params)
            return response
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            error_message = str(e)
            
            # Check if this is a throttling error
            if error_code in ['ThrottlingException', 'TooManyRequestsException', 'ServiceUnavailable'] or 'throttl' in error_message.lower() or 'too many tokens' in error_message.lower():
                retry_count += 1
                
                if retry_count > MAX_RETRIES:
                    logger.error(f"Max retries ({MAX_RETRIES}) exceeded. Giving up.")
                    raise
                
                # Calculate backoff with jitter (randomness to avoid thundering herd)
                jitter = random.uniform(0, 0.3 * backoff)
                wait_time = backoff + jitter
                
                logger.info(f"Request throttled. Retrying in {wait_time:.2f} seconds (attempt {retry_count}/{MAX_RETRIES})")
                time.sleep(wait_time)
                
                # Exponential backoff with higher multiplier
                backoff = min(backoff * BACKOFF_MULTIPLIER, 30)  # Cap at 30 seconds
            elif 'inference profile' in error_message.lower() and MODEL_ID == 'amazon.nova-premier-v1:0':
                # Special case for Nova Premier requiring an inference profile
                logger.error("Nova Premier requires an inference profile to be provisioned. Please create an inference profile in the Bedrock console and set the INFERENCE_PROFILE_ARN environment variable.")
                raise ValueError("Nova Premier requires a provisioned inference profile. Set INFERENCE_PROFILE_ARN environment variable with the ARN of your inference profile.")
            else:
                # Not a throttling error, re-raise
                raise

def lambda_handler(event, context):
    """
    Lambda function handler to extract highlights from a video using Amazon Nova Pro.
    
    Parameters:
    - event: Contains info about the S3 event trigger (transcription result uploaded)
    - context: Lambda execution context
    
    The function expects the transcription file to be uploaded to S3, which triggers this Lambda.
    It then retrieves the video file and transcript, invokes the Nova Pro model, and saves
    the highlights to S3.
    """
    # Get the object from the event
    bucket = event['Records'][0]['s3']['bucket']['name']
    transcript_key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'])
    
    # Validate the key is in the transcriptions/ prefix
    if not transcript_key.startswith('transcriptions/'):
        logger.info(f"Object {transcript_key} not in transcriptions/ prefix, skipping")
        return {
            'statusCode': 200,
            'body': json.dumps('File not in transcriptions/ prefix')
        }
    
    try:
        # Read the entire transcript filename
        # Format: transcriptions/{transcription_timestamp}-{video_timestamp}-{random_id}-{filename}.json
        transcript_filename = transcript_key.replace('transcriptions/', '').replace('.json', '')
        logger.info(f"Transcript filename: {transcript_filename}")
        
        # Generate output key for the highlights
        # Use the transcript filename to maintain traceability
        highlights_key = f"highlights/{transcript_filename}-highlights.json"
        
        # Check if highlights already exist (for idempotency) 
        try:
            s3.head_object(Bucket=HIGHLIGHTS_BUCKET, Key=highlights_key)
            logger.info(f"Highlights already exist at {highlights_key}, skipping processing")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Highlights already exist',
                    'highlights_key': highlights_key
                })
            }
        except Exception:
            # Highlights don't exist yet, proceed with processing
            logger.info(f"No existing highlights found at {highlights_key}, proceeding with processing")
        
        # Parse the transcript filename to extract the video timestamp, random ID, and original filename
        # Try different patterns to handle different naming formats
        
        # Pattern 1: {transcription_timestamp}-{video_timestamp}-{random_id}-{filename}
        pattern1 = r'^(\d+)-(\d+)-([a-f0-9]+)-(.+)$'
        match1 = re.match(pattern1, transcript_filename)
        
        # Pattern 2: {transcription_timestamp}-{filename}
        pattern2 = r'^(\d+)-(.+)$'
        match2 = re.match(pattern2, transcript_filename)
        
        video_key = None
        
        if match1:
            # Extract components
            transcription_timestamp = match1.group(1)
            video_timestamp = match1.group(2)
            random_id = match1.group(3)
            original_filename = match1.group(4)
            
            # Try to find the video with the exact name format
            expected_video_key = f"input-videos/{video_timestamp}-{random_id}-{original_filename}"
            logger.info(f"Looking for video file with exact key: {expected_video_key}")
            
            try:
                # Check if the exact file exists
                s3.head_object(Bucket=VIDEO_BUCKET, Key=expected_video_key)
                video_key = expected_video_key
                logger.info(f"Found video file with exact match: {video_key}")
            except Exception:
                # If not found, try listing files with the timestamp prefix
                logger.info(f"Exact match not found, searching with prefix: input-videos/{video_timestamp}")
                list_response = s3.list_objects_v2(
                    Bucket=VIDEO_BUCKET,
                    Prefix=f"input-videos/{video_timestamp}"
                )
                
                if 'Contents' in list_response and list_response['Contents']:
                    video_key = list_response['Contents'][0]['Key']
                    logger.info(f"Found video file with prefix: {video_key}")
        
        elif match2:
            # Simpler pattern for smaller test files
            transcription_timestamp = match2.group(1)
            original_filename = match2.group(2)
            
            # Try finding the video with the same filename
            logger.info(f"Looking for video file with original filename: {original_filename}")
            list_response = s3.list_objects_v2(
                Bucket=VIDEO_BUCKET,
                Prefix=f"input-videos/{original_filename}"
            )
            
            if 'Contents' in list_response and list_response['Contents']:
                video_key = list_response['Contents'][0]['Key']
                logger.info(f"Found video file with matching filename: {video_key}")
        
        # If no match found with patterns, try a more general search
        if not video_key:
            # Extract any timestamps that might be in the filename
            timestamp_pattern = r'(\d{14})'
            timestamp_matches = re.findall(timestamp_pattern, transcript_filename)
            
            for timestamp in timestamp_matches:
                logger.info(f"Searching with extracted timestamp: {timestamp}")
                list_response = s3.list_objects_v2(
                    Bucket=VIDEO_BUCKET,
                    Prefix=f"input-videos/{timestamp}"
                )
                
                if 'Contents' in list_response and list_response['Contents']:
                    video_key = list_response['Contents'][0]['Key']
                    logger.info(f"Found video file with timestamp: {video_key}")
                    break
        
        # If still no match, fall back to a broader search
        if not video_key:
            # List all video files and find the most recent one
            logger.info("No specific match found, looking for most recent video")
            list_response = s3.list_objects_v2(
                Bucket=VIDEO_BUCKET,
                Prefix="input-videos/"
            )
            
            if 'Contents' in list_response and list_response['Contents']:
                # Sort by last modified time and get the most recent
                sorted_files = sorted(
                    list_response['Contents'], 
                    key=lambda x: x['LastModified'],
                    reverse=True
                )
                
                # Filter for valid video formats
                video_extensions = ['.mp4', '.mov', '.avi', '.wmv', '.flac', '.wav', '.mp3']
                for file_obj in sorted_files:
                    file_key = file_obj['Key']
                    if any(file_key.lower().endswith(ext) for ext in video_extensions):
                        video_key = file_key
                        logger.info(f"Found most recent video file: {video_key}")
                        break
        
        if not video_key:
            raise ValueError(f"Could not find corresponding video file for transcript {transcript_key}")
        
        # Create the highlights folder if it doesn't exist
        try:
            s3.put_object(
                Bucket=HIGHLIGHTS_BUCKET,
                Key="highlights/",
                Body=""
            )
            logger.info("Created highlights folder")
        except Exception as e:
            logger.info(f"Highlights folder might already exist: {e}")
        
        # Get the transcript content
        transcript_response = s3.get_object(Bucket=TRANSCRIPT_BUCKET, Key=transcript_key)
        transcript_content = transcript_response['Body'].read().decode('utf-8')
        transcript_data = json.loads(transcript_content)
        
        # Extract transcript text from the AWS Transcribe format
        transcript_text = ""
        if 'results' in transcript_data and 'transcripts' in transcript_data['results']:
            transcript_text = transcript_data['results']['transcripts'][0]['transcript']
        
        # Get video format from the file extension
        video_format = "mp4"  # Default format
        if "." in video_key:
            ext = video_key.split(".")[-1].lower()
            if ext in ['mp4', 'mov', 'avi', 'wmv']:
                video_format = ext
        
        # Construct the input payload for the Amazon Nova Pro model
        payload = {
            "inferenceConfig": {
                "max_new_tokens": 1000
            },
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "text": "Extract key highlights from the following video. Use the provided transcript as additional context."
                        },
                        {
                            "video": {
                                "format": video_format,
                                "source": {
                                    "s3Location": {
                                        "uri": f"s3://{VIDEO_BUCKET}/{video_key}"
                                    }
                                }
                            }
                        },
                        {
                            "text": transcript_text
                        }
                    ]
                }
            ]
        }
        
        # Convert the payload to JSON string
        payload_json = json.dumps(payload)
        
        # Invoke the Amazon Nova Pro model with retry logic
        logger.info(f"Invoking Amazon Nova Pro model: {MODEL_ID}")
        response = invoke_with_retry(MODEL_ID, payload_json)
        
        # Parse the response
        response_body = json.loads(response['body'].read().decode())
        logger.info(f"Received response from model: {json.dumps(response_body)[:200]}...")
        
        # Extract the highlights from the response
        highlights = None
        if 'output' in response_body:
            if isinstance(response_body['output'], dict) and 'message' in response_body['output']:
                # Handle nested structure: {"output": {"message": {"content": [{"text": "..."}]}}}
                message = response_body['output']['message']
                if isinstance(message, dict) and 'content' in message and isinstance(message['content'], list):
                    for item in message['content']:
                        if isinstance(item, dict) and 'text' in item:
                            highlights = item['text']
                            break
                elif isinstance(response_body['output'], str):
                    # Handle simple string output
                    highlights = response_body['output']
                else:
                    # Handle dict or other type
                    highlights = json.dumps(response_body['output'])
            elif 'messages' in response_body and len(response_body['messages']) > 0:
                if response_body['messages'][0].get('content'):
                    for content_item in response_body['messages'][0]['content']:
                        if content_item.get('text'):
                            highlights = content_item['text']
                            break
            elif 'completion' in response_body:
                highlights = response_body['completion']
            elif 'content' in response_body:
                highlights = response_body['content']
            elif 'generated_text' in response_body:
                highlights = response_body['generated_text']
            elif isinstance(response_body, dict) and 'body' in response_body:
                # Sometimes the model returns a nested body field
                inner_body = response_body['body']
                if isinstance(inner_body, str):
                    highlights = inner_body
                elif isinstance(inner_body, dict):
                    highlights = json.dumps(inner_body)
        
        if not highlights and isinstance(response_body, str):
            highlights = response_body
        elif not highlights and isinstance(response_body, dict):
            # Last resort - convert entire response to JSON string
            highlights = json.dumps(response_body)
        
        # Safe logging that won't cause errors with slicing
        if highlights:
            if isinstance(highlights, str):
                preview = highlights[:100] + "..." if len(highlights) > 100 else highlights
            else:
                preview = str(highlights)[:100] + "..."
            logger.info(f"Extracted highlights: {preview}")
        else:
            logger.info("No highlights extracted: None")
        
        # Format the highlights as JSON
        highlights_data = {
            "video_key": video_key,
            "transcript_key": transcript_key,
            "timestamp": datetime.now().isoformat(),
            "model_id": MODEL_ID,
            "highlights": highlights
        }
        
        # Save the highlights to S3
        s3.put_object(
            Bucket=HIGHLIGHTS_BUCKET,
            Key=highlights_key,
            Body=json.dumps(highlights_data, indent=2),
            ContentType='application/json'
        )
        
        logger.info(f"Successfully extracted highlights and saved to {highlights_key}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Successfully extracted highlights',
                'highlights_key': highlights_key
            })
        }
    
    except Exception as e:
        logger.error(f"Error processing {transcript_key} from bucket {bucket}. Error: {str(e)}")
        raise e 