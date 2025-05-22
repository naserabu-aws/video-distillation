import React, { useState, useRef, useEffect } from 'react';
import { S3Client, PutObjectCommand, ListObjectsV2Command, HeadObjectCommand, GetObjectCommand } from '@aws-sdk/client-s3';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';

// S3 bucket name - must be set in environment variables
const S3_BUCKET = process.env.REACT_APP_S3_BUCKET;

// Initialize the S3 client
const s3Client = new S3Client({
  region: process.env.REACT_APP_AWS_REGION,
  credentials: {
    accessKeyId: process.env.REACT_APP_AWS_ACCESS_KEY_ID,
    secretAccessKey: process.env.REACT_APP_AWS_SECRET_ACCESS_KEY,
  },
});

function App() {
  const [file, setFile] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadStatus, setUploadStatus] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [highlightVideo, setHighlightVideo] = useState(null);
  const [s3Key, setS3Key] = useState('');
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef(null);
  const pollingIntervalRef = useRef(null);

  // Clean up polling interval on component unmount
  useEffect(() => {
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, []);

  // Handle file selection
  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile && selectedFile.type === 'video/mp4') {
      setFile(selectedFile);
      setUploadStatus('');
      setHighlightVideo(null);
    } else {
      setUploadStatus('error');
      setFile(null);
      alert('Please select an MP4 video file.');
    }
  };

  // Handle drag events
  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  // Handle drop event
  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile.type === 'video/mp4') {
        setFile(droppedFile);
        setUploadStatus('');
        setHighlightVideo(null);
      } else {
        setUploadStatus('error');
        setFile(null);
        alert('Please select an MP4 video file.');
      }
    }
  };

  // Handle file upload
  const handleUpload = async () => {
    if (!file) {
      alert('Please select a file first.');
      return;
    }

    try {
      setIsUploading(true);
      setUploadProgress(0);
      setUploadStatus('uploading');

      // Generate a unique filename with timestamp and random ID in the format YYYYMMDDHHMMSS-ID
      const now = new Date();
      const timestamp = now.getFullYear() +
        String(now.getMonth() + 1).padStart(2, '0') +
        String(now.getDate()).padStart(2, '0') +
        String(now.getHours()).padStart(2, '0') +
        String(now.getMinutes()).padStart(2, '0') +
        String(now.getSeconds()).padStart(2, '0');
      
      // Generate a longer ID similar to the highlight video format
      const randomId = Array.from(window.crypto.getRandomValues(new Uint8Array(12)))
        .map(b => b.toString(16).padStart(2, '0'))
        .join('');
      
      const cleanedFilename = file.name.replace(/[^a-zA-Z0-9._-]/g, '');
      const s3Key = `input-videos/${timestamp}-${randomId}-${cleanedFilename}`;
      setS3Key(s3Key);

      console.log('Generating presigned URL for S3 key:', s3Key);
      
      // Create the command to put the object in S3
      const command = new PutObjectCommand({
        Bucket: S3_BUCKET,
        Key: s3Key,
        ContentType: file.type,
      });
      
      // Generate a presigned URL for uploading
      const presignedUrl = await getSignedUrl(s3Client, command, { expiresIn: 3600 });
      console.log('Generated presigned URL:', presignedUrl);
      
      // Use XMLHttpRequest for upload progress tracking
      const xhr = new XMLHttpRequest();
      xhr.open('PUT', presignedUrl);
      xhr.setRequestHeader('Content-Type', file.type);
      
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) {
          const percentCompleted = Math.round((event.loaded * 100) / event.total);
          setUploadProgress(percentCompleted);
        }
      };
      
      xhr.onload = () => {
        if (xhr.status === 200) {
          console.log('Upload successful');
          setUploadStatus('success');
          setIsUploading(false);
          setIsProcessing(true);
          
          // Start polling for highlight video
          startPollingForHighlight(s3Key);
        } else {
          console.error('Upload failed with status:', xhr.status);
          throw new Error(`Upload failed with status: ${xhr.status}`);
        }
      };
      
      xhr.onerror = () => {
        console.error('Network error during upload');
        throw new Error('Upload failed due to network error');
      };
      
      xhr.send(file);
    } catch (error) {
      console.error('Error uploading file:', error);
      setUploadStatus('error');
      setIsUploading(false);
    }
  };

  // Poll for highlight video
  const startPollingForHighlight = (videoKey) => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
    }

    let attempts = 0;
    const maxAttempts = 30; // Poll for up to 5 minutes (30 * 10 seconds)

    pollingIntervalRef.current = setInterval(async () => {
      attempts++;
      console.log(`Polling for highlight video, attempt ${attempts}/${maxAttempts}`);
      
      try {
        // Try multiple patterns to find the highlight video
        
        // Extract info from the input video key
        // Format: input-videos/TIMESTAMP-ID-filename.mp4
        const keyParts = videoKey.split('/');
        const filename = keyParts[keyParts.length - 1];
        const filenameParts = filename.split('-');
        
        // List of possible highlight video patterns to check
        const highlightPatterns = [];
        
        // We'll rely on the list operation to find the correct highlight video
        // rather than trying to construct the exact path
        
        // Pattern 2: Fallback to check for any recent highlight videos
        // This is useful if the backend uses a different naming convention
        try {
          console.log("Attempting to list all highlight videos in the bucket");
          const listCommand = new ListObjectsV2Command({
            Bucket: S3_BUCKET,
            Prefix: 'highlight-videos/',
            MaxKeys: 20
          });
          
          const listResponse = await s3Client.send(listCommand);
          
          if (listResponse.Contents) {
            // Sort by last modified date (newest first)
            const sortedObjects = [...listResponse.Contents].sort((a, b) => 
              new Date(b.LastModified) - new Date(a.LastModified)
            );
            
            // Extract the input video ID (if available)
            let inputVideoId = null;
            if (filenameParts.length >= 2) {
              inputVideoId = filenameParts[1];
              console.log(`Input video ID: ${inputVideoId}`);
            }
            
            console.log(`Found ${sortedObjects.length} objects in highlight-videos/ prefix`);
            
            // Log all highlight videos for debugging
            sortedObjects.forEach((obj, index) => {
              if (obj.Key.endsWith('-highlights.mp4')) {
                console.log(`[${index}] ${obj.Key} (Last Modified: ${obj.LastModified})`);
              }
            });
            
            // Extract the original filename without extension
            const originalFilename = file.name.split('.')[0];
            console.log(`Original filename: ${originalFilename}`);
            
            // Extract timestamp and ID from the input video key
            const timestamp = filenameParts[0];
            const videoId = filenameParts[1];
            console.log(`Looking for highlight videos with timestamp: ${timestamp} and ID: ${videoId}`);
            
            // First priority: exact match with timestamp-id-originalname-highlights.mp4
            for (const obj of sortedObjects) {
              const expectedPattern = `${timestamp}-${videoId}-${originalFilename}-highlights.mp4`;
              if (obj.Key.endsWith(expectedPattern)) {
                highlightPatterns.unshift(obj.Key);
                console.log(`Found exact match highlight video: ${obj.Key}`);
              }
            }
            
            // Second priority: match with timestamp and ID
            if (timestamp && videoId) {
              for (const obj of sortedObjects) {
                const keyPattern = `${timestamp}-${videoId}`;
                if (obj.Key.includes(keyPattern) && obj.Key.endsWith('-highlights.mp4') && !highlightPatterns.includes(obj.Key)) {
                  highlightPatterns.unshift(obj.Key);
                  console.log(`Found highlight video with matching timestamp and ID: ${obj.Key}`);
                }
              }
            }
            
            // Third priority: match with just ID
            if (videoId) {
              for (const obj of sortedObjects) {
                if (obj.Key.includes(videoId) && obj.Key.endsWith('-highlights.mp4') && !highlightPatterns.includes(obj.Key)) {
                  highlightPatterns.push(obj.Key);
                  console.log(`Found highlight video with matching ID: ${obj.Key}`);
                }
              }
            }
            
            // Don't fall back to most recent video - only use videos that match our criteria
            if (highlightPatterns.length === 0) {
              console.log("No matching highlight videos found, will continue polling until timeout");
            }
            
            console.log(`Final highlight patterns to check (in order): ${JSON.stringify(highlightPatterns)}`);
          }
        } catch (error) {
          console.error("Error listing highlight videos:", error);
          // Continue with the patterns we already have
        }
        
        // Try each pattern until we find a valid highlight video
        let foundHighlight = false;
        for (const highlightKey of highlightPatterns) {
          console.log(`Checking for highlight video with key: ${highlightKey}`);
          
          try {
            // Check if the object exists in S3
            const headCommand = new HeadObjectCommand({
              Bucket: S3_BUCKET,
              Key: highlightKey
            });
            
            try {
              await s3Client.send(headCommand);
              
              // If we get here, the file exists - generate a presigned URL
              const getCommand = new GetObjectCommand({
                Bucket: S3_BUCKET,
                Key: highlightKey
              });
              
              const highlightUrl = await getSignedUrl(s3Client, getCommand, { expiresIn: 3600 });
              
              setHighlightVideo(highlightUrl);
              setIsProcessing(false);
              clearInterval(pollingIntervalRef.current);
              foundHighlight = true;
              console.log(`Found highlight video at: ${highlightKey}, generated presigned URL`);
              break;
            } catch (err) {
              console.log(`Highlight not found at ${highlightKey}`);
            }
          } catch (error) {
            console.log(`Error checking for highlight at ${highlightKey}:`, error);
          }
        }
        
        // If we've checked all patterns and still haven't found a highlight
        if (!foundHighlight) {
          console.log(`No highlight video found yet. Attempt ${attempts}/${maxAttempts}`);
          
          if (attempts >= maxAttempts) {
            setIsProcessing(false);
            setUploadStatus('error');
            clearInterval(pollingIntervalRef.current);
            alert('Highlight generation timed out. Please try again later.');
          }
        }
      } catch (error) {
        console.error('Error polling for highlight:', error);
        
        if (attempts >= maxAttempts) {
          setIsProcessing(false);
          setUploadStatus('error');
          clearInterval(pollingIntervalRef.current);
          alert('Highlight generation timed out. Please try again later.');
        }
      }
    }, 10000); // Poll every 10 seconds
  };

  return (
    <div className="container">
      <div className="header">
        <h1>Video Highlights Generator</h1>
      </div>
      
      <div className="upload-container">
        <div 
          className={`drop-zone ${dragActive ? 'active' : ''}`}
          onClick={() => fileInputRef.current.click()}
          onDragEnter={handleDrag}
          onDragOver={handleDrag}
          onDragLeave={handleDrag}
          onDrop={handleDrop}
        >
          <input 
            type="file" 
            ref={fileInputRef}
            onChange={handleFileChange}
            accept="video/mp4"
            style={{ display: 'none' }}
          />
          {file ? (
            <p>Selected file: {file.name}</p>
          ) : (
            <p>Drag and drop an MP4 video file here, or click to select a file</p>
          )}
        </div>
        
        {file && !isUploading && !isProcessing && !highlightVideo && (
          <button 
            onClick={handleUpload}
            style={{
              padding: '10px 20px',
              backgroundColor: '#007bff',
              color: 'white',
              border: 'none',
              borderRadius: '5px',
              cursor: 'pointer',
              fontSize: '16px',
              width: '100%'
            }}
          >
            Upload Video
          </button>
        )}
        
        {isUploading && (
          <div className="progress-container">
            <div className="progress-bar">
              <div 
                className="progress-bar-fill" 
                style={{ width: `${uploadProgress}%` }}
              ></div>
            </div>
            <p>Uploading: {uploadProgress}%</p>
          </div>
        )}
        
        {uploadStatus === 'success' && !isProcessing && !highlightVideo && (
          <div className="status-message success">
            <p>Upload successful!</p>
          </div>
        )}
        
        {uploadStatus === 'error' && (
          <div className="status-message error">
            <p>Error uploading file. Please try again.</p>
          </div>
        )}
        
        {isProcessing && (
          <div className="status-message info">
            <p>Processing transcription and highlights... This may take a few minutes.</p>
          </div>
        )}
        
        {highlightVideo && (
          <div className="video-container">
            <h2>Your Highlight Video</h2>
            <video controls>
              <source src={highlightVideo} type="video/mp4" />
              Your browser does not support the video tag.
            </video>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
