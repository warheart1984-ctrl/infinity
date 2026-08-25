import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import ImageGenerator from './ImageGenerator';

vi.mock('../lib/api', () => ({
  apiPost: vi.fn(),
  getApiErrorMessage: vi.fn((error, fallback) => fallback || error?.message || 'Request failed'),
}));

vi.mock('../lib/history', () => ({
  addHistoryEntry: vi.fn(),
}));

vi.mock('react-hot-toast', () => ({
  default: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

function renderImage(path = '/image-generator') {
  return render(
    <MemoryRouter initialEntries={[path]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <ImageGenerator />
    </MemoryRouter>,
  );
}

describe('ImageGenerator', () => {
  afterEach(() => {
    cleanup();
  });

  it('opens img2img when the model-library query is present', () => {
    renderImage('/image-generator?mode=img2img');

    expect(screen.getByRole('button', { name: 'Image → Image' }).className).toContain('active');
    expect(screen.getByText('Source image')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Transform Image' })).toBeTruthy();
  });
});
