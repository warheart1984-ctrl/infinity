import React, { useState } from 'react';
import toast from 'react-hot-toast';
import { apiPost, getApiErrorMessage } from '../lib/api';
import { addHistoryEntry } from '../lib/history';
import './ImageGenerator.css';

function ImageGenerator() {
  const [prompt, setPrompt] = useState('');
  const [steps, setSteps] = useState(50);
  const [loading, setLoading] = useState(false);
  const [generatedImage, setGeneratedImage] = useState('');
  const [statusNote, setStatusNote] = useState(
    'SD-Turbo on your RX 580 (Vulkan) is ready. Describe an image and render.'
  );

  const handleGenerate = async () => {
    if (!prompt.trim()) {
      toast.error('Please enter a prompt');
      return;
    }

    setLoading(true);
    try {
      const response = await apiPost('/api/image/generate', {
        prompt,
        prompt_size: '512x512', num_inference_steps: steps
      });
      setGeneratedImage(`data:image/png;base64,${response.data.image}`);
      setStatusNote('Image generation is active for this run.');
      addHistoryEntry({
        type: 'image',
        prompt,
        output: 'Generated image preview',
        model: 'SD-Turbo Vulkan',
      });
      toast.success('Image generated successfully!');
    } catch (error) {
      setStatusNote(getApiErrorMessage(error));
      toast.error(`Error generating image: ${getApiErrorMessage(error)}`);
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = () => {
    const link = document.createElement('a');
    link.href = generatedImage;
    link.download = 'generated-image.png';
    link.click();
    toast.success('Image downloaded!');
  };

  return (
    <div className="image-generator">
      <div className="page-intro">
        <h1>Image Generator</h1>
        <p>Generate a local preview image and validate binary payload handling end to end.</p>
      </div>
      
      <div className="generator-container">
        <div className="input-section page-panel">
          <label>Image Description</label>
          <div className="feature-note">
            {statusNote}
          </div>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Describe the image you want to generate..."
            rows="6"
          />

          <div className="controls">
            <div className="control-group">
              <label>Inference Steps: {steps}</label>
              <input
                type="range"
                min="10"
                max="100"
                value={steps}
                onChange={(e) => setSteps(Number(e.target.value))}
              />
            </div>
          </div>

          <button
            className="generate-btn"
            onClick={handleGenerate}
            disabled={loading}
          >
            {loading ? 'Generating...' : 'Generate Image'}
          </button>
        </div>

        {generatedImage && (
          <div className="output-section page-panel">
            <h2>Generated Image</h2>
            <img src={generatedImage} alt="Generated" className="generated-image" />
            <button className="download-btn" onClick={handleDownload}>
              Download Image
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default ImageGenerator;
