import React, { useState } from 'react';
import axios from 'axios';
import config from './config';
import './App.css';

function App() {
  const [file, setFile] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadStatus, setUploadStatus] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [detailedError, setDetailedError] = useState(null);

  const handleFileChange = (e) => {
    if (e.target.files[0]) {
      setFile(e.target.files[0]);
      setUploadStatus('');
      setUploadProgress(0);
      setDetailedError(null);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!file) {
      setUploadStatus('Please select a video file first.');
      return;
    }

    try {
      setIsUploading(true);
      setUploadStatus('Requesting presigned URL...');
      setDetailedError(null);

      // Step 1: Request presigned URL from backend
      const response = await axios.post(config.API_ENDPOINT, 
        {
          fileName: file.name,
          contentType: file.type
        },
        {
          headers: {
            'Content-Type': 'application/json'
          }
        }
      );

      console.log('API Response:', response.data);

      // Check the response structure
      console.log('Full response structure:', JSON.stringify(response.data));
      
      // The Lambda returns presigned URL as 'presignedUrl' or maybe something else
      let presignedUrl;
      
      if (response.data.presignedUrl) {
        presignedUrl = response.data.presignedUrl;
      } else if (response.data.s3Key && response.data.bucket) {
        // If the structure is different, check other fields
        console.warn('Using alternative response fields - actual structure may differ');
        throw new Error('Response structure is different than expected. Check console for details.');
      } else {
        throw new Error('Invalid response from server. Missing presigned URL.');
      }

      // Step 2: Upload file directly to S3 using presigned URL
      setUploadStatus('Uploading file to S3...');
      
      await axios.put(presignedUrl, file, {
        headers: {
          'Content-Type': file.type
        },
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setUploadProgress(percentCompleted);
        }
      });

      setUploadStatus('Upload complete! Processing will happen automatically in the background.');
    } catch (error) {
      console.error('Error during process:', error);
      
      let errorMsg = 'An error occurred.';
      
      if (error.response) {
        // The request was made and the server responded with a status code
        // that falls out of the range of 2xx
        console.error('Error response:', error.response);
        errorMsg = `Server error: ${error.response.status} ${error.response.statusText}`;
        setDetailedError(error.response.data);
      } else if (error.request) {
        // The request was made but no response was received
        console.error('Error request:', error.request);
        errorMsg = 'No response from server. Check your network connection.';
      } else {
        // Something happened in setting up the request that triggered an Error
        errorMsg = error.message;
      }
      
      setUploadStatus(`Error: ${errorMsg}`);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="app-container">
      <h1>Video Transcription Tool</h1>
      <form onSubmit={handleSubmit}>
        <div className="file-input">
          <label htmlFor="video-file">Select Video File:</label>
          <input 
            type="file" 
            id="video-file" 
            accept="video/*" 
            onChange={handleFileChange}
            disabled={isUploading}
          />
        </div>
        
        {file && (
          <div className="file-info">
            <p>Selected file: {file.name}</p>
            <p>File size: {(file.size / (1024 * 1024)).toFixed(2)} MB</p>
          </div>
        )}
        
        <button 
          type="submit" 
          className="submit-button" 
          disabled={!file || isUploading}
        >
          Upload Video
        </button>
      </form>
      
      {uploadProgress > 0 && (
        <div className="progress-container">
          <div className="progress-bar">
            <div className="progress" style={{ width: `${uploadProgress}%` }}></div>
          </div>
          <p>{uploadProgress}%</p>
        </div>
      )}
      
      {uploadStatus && (
        <div className="status-message">
          <p>{uploadStatus}</p>
        </div>
      )}
      
      {detailedError && (
        <div className="error-details">
          <p><strong>Technical details:</strong></p>
          <pre>{JSON.stringify(detailedError, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}

export default App; 