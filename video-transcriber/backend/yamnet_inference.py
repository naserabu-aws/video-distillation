import json
import numpy as np
import tensorflow as tf
import os
import librosa
import soundfile as sf

def model_fn(model_dir):
    """Load the YAMNet model"""
    print(f"Loading model from {model_dir}")
    model = tf.saved_model.load(model_dir)
    
    # Load class labels
    with open(os.path.join(model_dir, 'class_labels.json'), 'r') as f:
        class_names = json.load(f)
    
    return {"model": model, "class_names": class_names}

def input_fn(request_body, request_content_type):
    """Parse input data for inference"""
    print(f"Received request with content type: {request_content_type}")
    
    if request_content_type == 'application/octet-stream':
        # Expecting audio file bytes
        # Save as temporary file
        temp_audio_path = '/tmp/audio.wav'
        with open(temp_audio_path, 'wb') as f:
            f.write(request_body)
        
        # Extract audio from file
        try:
            # Try to load with soundfile first
            audio, sample_rate = sf.read(temp_audio_path)
            if len(audio.shape) > 1:  # Multi-channel, convert to mono
                audio = np.mean(audio, axis=1)
        except:
            # Fall back to librosa
            audio, sample_rate = librosa.load(temp_audio_path, sr=16000, mono=True)
        
        # Resample to 16kHz if needed
        if sample_rate != 16000:
            audio = librosa.resample(audio, orig_sr=sample_rate, target_sr=16000)
        
        return audio
    else:
        raise ValueError(f"Unsupported content type: {request_content_type}")

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