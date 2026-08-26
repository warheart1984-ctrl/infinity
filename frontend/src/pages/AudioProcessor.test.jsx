import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import AudioProcessor from './AudioProcessor';

const audioMocks = vi.hoisted(() => ({
  apiPost: vi.fn(),
  getApiErrorMessage: vi.fn((error, fallback) => fallback || error?.message || 'Request failed'),
  addHistoryEntry: vi.fn(),
  setPendingJarvisDraft: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock('../lib/api', () => ({
  apiPost: audioMocks.apiPost,
  getApiErrorMessage: audioMocks.getApiErrorMessage,
}));

vi.mock('../lib/history', () => ({
  addHistoryEntry: audioMocks.addHistoryEntry,
}));

vi.mock('../lib/jarvis', () => ({
  setPendingJarvisDraft: audioMocks.setPendingJarvisDraft,
}));

vi.mock('react-hot-toast', () => ({
  default: {
    success: audioMocks.toastSuccess,
    error: audioMocks.toastError,
  },
}));

function renderAudio(path = '/audio-processor') {
  return render(
    <MemoryRouter initialEntries={[path]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <AudioProcessor />
    </MemoryRouter>,
  );
}

describe('AudioProcessor', () => {
  beforeEach(() => {
    audioMocks.apiPost.mockReset();
    audioMocks.addHistoryEntry.mockReset();
    audioMocks.setPendingJarvisDraft.mockReset();
    audioMocks.toastSuccess.mockReset();
    audioMocks.toastError.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it('opens the STT lane from the model-library query', () => {
    renderAudio('/audio-processor?lane=stt');

    expect(screen.getByRole('tab', { name: 'Transcribe' }).getAttribute('aria-selected')).toBe('true');
    expect(screen.getByRole('button', { name: 'Transcribe' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Ask from audio' })).toBeTruthy();
  });

  it('opens the TTS lane and posts synthesize payloads', async () => {
    audioMocks.apiPost.mockResolvedValue({ data: { audio: 'dGVzdA==', format: 'wav' } });
    renderAudio('/audio-processor?lane=tts');

    fireEvent.change(screen.getByPlaceholderText(/Type the line Jarvis should speak/i), {
      target: { value: 'Hello operator' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Synthesize' }));

    expect(audioMocks.apiPost).toHaveBeenCalledWith('/api/audio/synthesize', { text: 'Hello operator' });
    expect(await screen.findByText('Download WAV')).toBeTruthy();
  });

  it('opens the music lane from ?lane=music', () => {
    renderAudio('/audio-processor?lane=music');

    expect(screen.getByRole('tab', { name: 'Music' }).getAttribute('aria-selected')).toBe('true');
    expect(screen.getByRole('button', { name: 'Generate Music' })).toBeTruthy();
  });
});
