import React, { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { Link, useSearchParams } from 'react-router-dom';
import { apiPost, getApiErrorMessage } from '../lib/api';
import { addHistoryEntry } from '../lib/history';
import './ImageGenerator.css';

function modeFromSearch(value) {
  return value === 'img2img' ? 'img2img' : 'text2img';
}

function ImageGenerator() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [mode, setMode] = useState(() => modeFromSearch(searchParams.get('mode')));
  const [prompt, setPrompt] = useState('');
  const [steps, setSteps] = useState(40);
  const [strength, setStrength] = useState(0.65);
  const [sourceFile, setSourceFile] = useState(null);
  const [sourcePreview, setSourcePreview] = useState('');
  const [loading, setLoading] = useState(false);
  const [generatedImage, setGeneratedImage] = useState('');
  const [statusNote, setStatusNote] = useState(
    'Text-to-image and image-to-image both use the local Diffusers path (disabled on laptop preset until you enable it).'
  );

  useEffect(() => {
    setMode(modeFromSearch(searchParams.get('mode')));
  }, [searchParams]);

  const selectMode = (nextMode) => {
    const resolved = modeFromSearch(nextMode);
    setMode(resolved);
    setSearchParams({ mode: resolved }, { replace: true });
  };

  const handleSourceSelect = (event) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    setSourceFile(file);
    setSourcePreview(URL.createObjectURL(file));
  };

  const handleGenerate = async () => {
    if (!prompt.trim()) {
      toast.error('Please enter a prompt');
      return;
    }
    if (mode === 'img2img' && !sourceFile) {
      toast.error('Please select a source image for img2img');
      return;
    }

    setLoading(true);
    try {
      let response;
      if (mode === 'img2img') {
        const formData = new FormData();
        formData.append('prompt', prompt);
        formData.append('image', sourceFile);
        formData.append('num_inference_steps', String(steps));
        formData.append('strength', String(strength));
        response = await apiPost('/api/image/img2img', formData);
      } else {
        response = await apiPost('/api/image/generate', {
          prompt,
          num_inference_steps: steps,
        });
      }
      setGeneratedImage(`data:image/png;base64,${response.data.image}`);
      setStatusNote(mode === 'img2img' ? 'Img2img completed.' : 'Text-to-image completed.');
      addHistoryEntry({
        type: 'image',
        prompt,
        output: mode === 'img2img' ? 'Img2img preview' : 'Generated image preview',
        model: mode === 'img2img' ? 'AAIS img2img' : 'AAIS local API',
      });
      toast.success(mode === 'img2img' ? 'Image transformed!' : 'Image generated!');
    } catch (error) {
      setStatusNote(getApiErrorMessage(error));
      toast.error(`Error: ${getApiErrorMessage(error)}`);
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = () => {
    const link = document.createElement('a');
    link.href = generatedImage;
    link.download = mode === 'img2img' ? 'img2img.png' : 'generated-image.png';
    link.click();
    toast.success('Image downloaded!');
  };

  return (
    <div className="image-generator">
      <div className="page-intro">
        <h1>Image Generator</h1>
        <p>
          Text-to-image and image-to-image on the local Diffusers stack.{' '}
          <Link to="/model-library">Browse Model Library</Link>
        </p>
      </div>

      <div className="generator-container">
        <div className="input-section page-panel">
          <div className="image-mode-toggle" role="tablist" aria-label="Image mode">
            <button
              type="button"
              className={mode === 'text2img' ? 'active' : ''}
              onClick={() => selectMode('text2img')}
            >
              Text → Image
            </button>
            <button
              type="button"
              className={mode === 'img2img' ? 'active' : ''}
              onClick={() => selectMode('img2img')}
            >
              Image → Image
            </button>
          </div>

          <label>Prompt</label>
          <div className="feature-note">{statusNote}</div>
          <textarea
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            placeholder={
              mode === 'img2img'
                ? 'Describe how to transform the source image...'
                : 'Describe the image you want to generate...'
            }
            rows="6"
          />

          {mode === 'img2img' ? (
            <div className="img2img-source">
              <label>Source image</label>
              <input type="file" accept="image/*" onChange={handleSourceSelect} />
              {sourcePreview ? (
                <img src={sourcePreview} alt="Source" className="source-preview" />
              ) : null}
            </div>
          ) : null}

          <div className="controls">
            <div className="control-group">
              <label>Inference Steps: {steps}</label>
              <input
                type="range"
                min="10"
                max="100"
                value={steps}
                onChange={(event) => setSteps(Number(event.target.value))}
              />
            </div>
            {mode === 'img2img' ? (
              <div className="control-group">
                <label>Strength: {strength.toFixed(2)}</label>
                <input
                  type="range"
                  min="0.1"
                  max="1"
                  step="0.05"
                  value={strength}
                  onChange={(event) => setStrength(Number(event.target.value))}
                />
              </div>
            ) : null}
          </div>

          <button className="generate-btn" onClick={handleGenerate} disabled={loading}>
            {loading ? 'Working…' : mode === 'img2img' ? 'Transform Image' : 'Generate Image'}
          </button>
        </div>

        {generatedImage ? (
          <div className="output-section page-panel">
            <h2>{mode === 'img2img' ? 'Transformed Image' : 'Generated Image'}</h2>
            <img src={generatedImage} alt="Result" className="generated-image" />
            <button className="download-btn" onClick={handleDownload}>
              Download Image
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}

export default ImageGenerator;
