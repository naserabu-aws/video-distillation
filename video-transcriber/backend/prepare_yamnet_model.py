import os
import json
import tensorflow as tf
import tensorflow_hub as hub
import numpy as np
import boto3
import tarfile
import shutil

def download_yamnet():
    """Download YAMNet model from TensorFlow Hub and prepare for SageMaker"""
    print("Downloading YAMNet model...")
    # Create directories
    os.makedirs('model/1', exist_ok=True)
    
    # Download model from TensorFlow Hub
    model = hub.load('https://tfhub.dev/google/yamnet/1')
    
    # Save model in SavedModel format for TensorFlow Serving
    tf.saved_model.save(model, 'model/1')
    
    # Create a labels file with the 521 AudioSet classes
    class_map_path = model.class_map_path().numpy().decode('utf-8')
    class_names = []
    with open(class_map_path) as f:
        for line in f:
            class_names.append(line.strip().split(',')[2])
    
    with open('model/class_labels.json', 'w') as f:
        json.dump(class_names, f)
    
    print("Model downloaded and saved to model/1")
    print("Class labels saved to model/class_labels.json")
    
    # Create a tar.gz archive
    with tarfile.open('model.tar.gz', 'w:gz') as tar:
        tar.add('model', arcname='.')
    
    print("Model packaged as model.tar.gz")
    
    # Upload to S3
    bucket_name = 'video-transcription-bucket-1747461583'
    s3_client = boto3.client('s3')
    
    s3_prefix = 'models/yamnet'
    s3_client.upload_file('model.tar.gz', bucket_name, f'{s3_prefix}/model.tar.gz')
    
    print(f"Model uploaded to s3://{bucket_name}/{s3_prefix}/model.tar.gz")
    
    # Clean up
    shutil.rmtree('model')
    os.remove('model.tar.gz')
    
    return f"s3://{bucket_name}/{s3_prefix}/model.tar.gz"

if __name__ == "__main__":
    model_path = download_yamnet()
    print(f"YAMNet model prepared and uploaded to {model_path}") 