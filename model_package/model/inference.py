import json
import numpy as np
import tensorflow as tf
import os
import librosa
import soundfile as sf
import tempfile
import subprocess
import urllib.parse
from io import BytesIO

def model_fn(model_dir):
    """Load the YAMNet model"""
    print(f"Loading model from {model_dir}")
    model = tf.saved_model.load(model_dir)
    
    # Load class labels
    with open(os.path.join(model_dir, 'class_labels.json'), 'r') as f:
        class_names = json.load(f)
    
    return {"model": model, "class_names": class_names}

def input_fn(request_body, request_content_type):
    """Parse input data for inference
    
    This function now handles:
    - application/octet-stream: Raw audio/video files (.mp4, .wav, etc.)
    - application/x-npy: NumPy array files
    - application/json: JSON with S3 path or base64 encoded audio/video
    """
    print(f"Received request with content type: {request_content_type}")
    
    if request_content_type == 'application/octet-stream':
        # Expecting raw audio/video file bytes
        return preprocess_audio_video(request_body)
    
    elif request_content_type == 'application/x-npy':
        # Expecting NumPy array
        try:
            # Load the NumPy array directly
            audio = np.load(BytesIO(request_body))
            return audio
        except Exception as e:
            print(f"Error loading NumPy array: {e}")
            raise ValueError(f"Failed to load NumPy array: {e}")
    
    elif request_content_type == 'application/json':
        # Expecting JSON with S3 path or base64 encoded data
        try:
            request = json.loads(request_body.decode('utf-8'))
            
            if 's3_uri' in request:
                # Extract bucket and key from S3 URI
                s3_uri = request['s3_uri']
                parsed_url = urllib.parse.urlparse(s3_uri)
                bucket = parsed_url.netloc
                key = parsed_url.path.lstrip('/')
                
                # Import boto3 here to avoid loading it unless needed
                import boto3
                s3 = boto3.client('s3')
                
                with tempfile.NamedTemporaryFile() as temp_file:
                    s3.download_fileobj(bucket, key, temp_file)
                    temp_file.flush()
                    temp_file.seek(0)
                    return preprocess_audio_video(temp_file.read())
            
            elif 'base64_data' in request:
                # Handle base64 encoded data
                import base64
                decoded_data = base64.b64decode(request['base64_data'])
                return preprocess_audio_video(decoded_data)
            
            else:
                raise ValueError("JSON request must contain either 's3_uri' or 'base64_data' field")
        
        except Exception as e:
            print(f"Error processing JSON request: {e}")
            raise ValueError(f"Failed to process JSON request: {e}")
    
    else:
        raise ValueError(f"Unsupported content type: {request_content_type}")

def preprocess_audio_video(binary_data):
    """Process audio/video data for YAMNet
    
    This function:
    1. Detects if input is audio or video
    2. Extracts audio from video if needed
    3. Resamples to 16kHz mono
    4. Returns a NumPy array ready for YAMNet
    """
    # Set up a temporary directory for processing
    with tempfile.TemporaryDirectory() as temp_dir:
        # Save input data to a temporary file
        input_path = os.path.join(temp_dir, "input_file")
        with open(input_path, 'wb') as f:
            f.write(binary_data)
        
        # First try to load as audio with librosa
        try:
            print("Attempting to load as audio file with librosa...")
            audio, sample_rate = librosa.load(input_path, sr=16000, mono=True)
            print(f"Successfully loaded audio with shape {audio.shape}, sample rate {sample_rate}")
            return audio
        except Exception as audio_error:
            print(f"Could not load as audio directly: {audio_error}")
            
            # Try to load with soundfile
            try:
                print("Attempting to load as audio file with soundfile...")
                audio, sample_rate = sf.read(input_path)
                if len(audio.shape) > 1:  # Multi-channel, convert to mono
                    audio = np.mean(audio, axis=1)
                
                # Resample to 16kHz if needed
                if sample_rate != 16000:
                    audio = librosa.resample(audio, orig_sr=sample_rate, target_sr=16000)
                
                print(f"Successfully loaded audio with shape {audio.shape}, sample rate {sample_rate}")
                return audio
            except Exception as sf_error:
                print(f"Could not load as audio with soundfile: {sf_error}")
        
        # If we get here, try to extract audio from video using ffmpeg
        try:
            print("Attempting to extract audio from video using ffmpeg...")
            audio_path = os.path.join(temp_dir, "audio.wav")
            
            # Try to find ffmpeg
            ffmpeg_binary = 'ffmpeg'
            if not os.path.exists('/usr/bin/ffmpeg'):
                print("ffmpeg not found in /usr/bin, using 'ffmpeg' from PATH")
            
            # Extract audio using ffmpeg
            subprocess.check_call([
                ffmpeg_binary, "-i", input_path,
                "-ac", "1", "-ar", "16000",
                "-y", audio_path
            ])
            
            # Load the extracted audio
            try:
                # Try with soundfile first
                audio, sample_rate = sf.read(audio_path)
                if len(audio.shape) > 1:  # Multi-channel, convert to mono
                    audio = np.mean(audio, axis=1)
            except:
                # Fall back to librosa
                audio, sample_rate = librosa.load(audio_path, sr=16000, mono=True)
            
            # Ensure audio is normalized to [-1.0, 1.0]
            if np.abs(audio).max() > 1.0:
                audio = audio / np.abs(audio).max()
            
            print(f"Successfully extracted and loaded audio with shape {audio.shape}")
            return audio
            
        except Exception as ffmpeg_error:
            print(f"Failed to extract audio from video: {ffmpeg_error}")
            raise ValueError(f"Could not process input as audio or video: {ffmpeg_error}")

def predict_fn(input_data, model_dict):
    """Run prediction with the YAMNet model"""
    model = model_dict["model"]
    class_names = model_dict["class_names"]
    
    # YAMNet expects audio to be 16kHz mono, normalized to [-1.0, 1.0]
    # Ensuring audio is normalized
    if np.abs(input_data).max() > 1.0:
        input_data = input_data / np.abs(input_data).max()
    
    # Make prediction - YAMNet returns scores, embeddings, spectrogram
    scores, embeddings, spectrogram = model(input_data)
    
    # Convert scores to NumPy array
    scores_np = scores.numpy()
    
    # Get top 10 predictions
    top_indices = np.argsort(scores_np[0])[-10:][::-1]
    top_scores = scores_np[0][top_indices]
    top_classes = [class_names[i] for i in top_indices]
    
    results = {
        "predictions": [
            {"class": cls, "score": float(score)} 
            for cls, score in zip(top_classes, top_scores)
        ],
        "raw_scores": scores_np[0].tolist(),
        "timestamp": "0.0"  # Default timestamp for the entire file
    }
    
    return results

def output_fn(prediction, response_content_type):
    """Format the prediction output"""
    if response_content_type == 'application/json':
        return json.dumps(prediction)
    else:
        return json.dumps(prediction)
