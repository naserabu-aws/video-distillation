import json
import boto3
import os
import uuid
from datetime import datetime
import time

s3_client = boto3.client('s3')
BUCKET_NAME = os.environ['BUCKET_NAME']

def lambda_handler(event, context):
    try:
        # Parse request body
        body = json.loads(event['body']) if event.get('body') else {}
        
        # Get filename from request
        file_name = body.get('fileName', '')
        content_type = body.get('contentType', 'video/mp4')
        
        if not file_name:
            return {
                'statusCode': 400,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'POST, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Content-Type': 'application/json'
                },
                'body': json.dumps({'error': 'fileName is required'})
            }
        
        # Generate a unique key for the file
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        random_id = uuid.uuid4().hex[:8]
        
        # Clean the filename and ensure it has an extension
        cleaned_filename = os.path.basename(file_name)
        
        # Create the S3 key with input-videos/ prefix
        s3_key = f"input-videos/{timestamp}-{random_id}-{cleaned_filename}"
        
        # Generate presigned URL with longer expiration (15 minutes) to handle large files
        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': BUCKET_NAME,
                'Key': s3_key,
                'ContentType': content_type
            },
            ExpiresIn=900  # 15 minutes
        )
        
        # Return the presigned URL and S3 key to the client
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'presignedUrl': presigned_url,
                's3Key': s3_key,
                'bucket': BUCKET_NAME
            })
        }
        
    except Exception as e:
        print(f"Error generating presigned URL: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({'error': str(e)})
        }

# Handle OPTIONS request for CORS
def handle_options():
    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Content-Type': 'application/json'
        },
        'body': json.dumps({})
    } 