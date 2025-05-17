FROM tensorflow/tensorflow:2.13.0-gpu

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    python3-pip \
    python3-setuptools \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir \
    sagemaker-training \
    tensorflow-hub==0.15.0 \
    librosa==0.10.1 \
    soundfile==0.12.1 \
    numpy==1.24.3 \
    scipy==1.10.1

# Set working directory
WORKDIR /opt/ml/code

# Copy inference script
COPY yamnet_inference.py /opt/ml/code/inference.py

# Entry point for SageMaker
ENTRYPOINT ["python3", "-m", "sagemaker_tensorflow_serving_container.serving"] 