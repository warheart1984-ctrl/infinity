import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import ModelLibrary from './ModelLibrary';

const modelLibraryMocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  getApiErrorMessage: vi.fn((error, fallback) => fallback || error?.message || 'Request failed'),
  toastError: vi.fn(),
}));

vi.mock('../lib/api', () => ({
  apiGet: modelLibraryMocks.apiGet,
  getApiErrorMessage: modelLibraryMocks.getApiErrorMessage,
}));

vi.mock('react-hot-toast', () => ({
  default: {
    error: modelLibraryMocks.toastError,
    success: vi.fn(),
  },
}));

function renderLibrary() {
  return render(
    <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <ModelLibrary />
    </MemoryRouter>,
  );
}

describe('ModelLibrary', () => {
  beforeEach(() => {
    modelLibraryMocks.apiGet.mockReset();
    modelLibraryMocks.toastError.mockReset();
    modelLibraryMocks.apiGet.mockResolvedValue({
      data: {
        entries: [
          {
            id: 'music.hf.musicgen_small',
            label: 'MusicGen Small',
            modality: 'music',
            provider_id: 'huggingface',
            provider_enabled: true,
            model_id: 'facebook/musicgen-small',
            status: 'available',
            summary: 'Open music generation.',
            tags: ['hf', 'music'],
          },
          {
            id: 'music.local.beatbox',
            label: 'Beatbox Adaptive Score',
            modality: 'music',
            provider_id: 'local',
            provider_enabled: true,
            model_id: 'arrangement_pcm.v1',
            status: 'available',
            summary: 'Deterministic adaptive score.',
            tags: ['beatbox'],
          },
          {
            id: 'voice.stt.whisper_base',
            label: 'Whisper Base (STT)',
            modality: 'voice_stt',
            provider_id: 'local',
            provider_enabled: true,
            model_id: 'whisper-base',
            status: 'available',
            summary: 'Local Whisper transcription.',
          },
        ],
        free_cloud_chat_failover_order: ['nvidia', 'local'],
      },
    });
  });

  afterEach(() => {
    cleanup();
  });

  it('wires catalog entries to live operator surfaces', async () => {
    renderLibrary();

    expect((await screen.findByRole('link', { name: 'Open music generator' })).getAttribute('href')).toBe(
      '/audio-processor?lane=music',
    );
    expect(screen.getByRole('link', { name: 'Open adaptive score' }).getAttribute('href')).toBe(
      '/adaptive-music',
    );
    expect(screen.getByRole('link', { name: 'Open transcription' }).getAttribute('href')).toBe(
      '/audio-processor?lane=stt',
    );
    expect(screen.getByRole('link', { name: 'Image / Img2Img' }).getAttribute('href')).toBe(
      '/image-generator',
    );
  });
});
