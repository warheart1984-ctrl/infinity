import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import AdaptiveMusic from './AdaptiveMusic';

const adaptiveMocks = vi.hoisted(() => ({
  apiPost: vi.fn(),
  getApiErrorMessage: vi.fn((error, fallback) => fallback || error?.message || 'Request failed'),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock('../lib/api', () => ({
  apiPost: adaptiveMocks.apiPost,
  getApiErrorMessage: adaptiveMocks.getApiErrorMessage,
}));

vi.mock('react-hot-toast', () => ({
  default: {
    success: adaptiveMocks.toastSuccess,
    error: adaptiveMocks.toastError,
  },
}));

function renderPage() {
  return render(
    <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <AdaptiveMusic />
    </MemoryRouter>,
  );
}

describe('AdaptiveMusic', () => {
  beforeEach(() => {
    adaptiveMocks.apiPost.mockReset();
    adaptiveMocks.toastSuccess.mockReset();
    adaptiveMocks.toastError.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it('posts scene state to the adaptive compose API and plays the mix', async () => {
    adaptiveMocks.apiPost.mockResolvedValue({
      data: {
        mood: 'intense',
        bpm: 140,
        duration_sec: 6,
        engine: 'arrangement_pcm.v1',
        mix_sha256: 'abc123def456',
        stems: { mix: 'UklGRg==', kick: 'UklGRg==' },
        mandala_visual_plan: {
          plan_id: 'mvap_deadbeefcafebabe',
          plan_version: 'mandala_visual_adaptation.v1',
          consumer_seam: { owns_pixels: false, status: 'plan_only' },
          renderer_hooks: {
            lighting_intensity: 0.82,
            lighting_hue_deg: 15,
            lighting_temperature: 'warm',
            camera_pulse_hz: 2.3333,
            camera_motion_amplitude: 0.75,
            camera_motion: 'handheld pulse',
            particle_energy: 0.71,
            particle_density: 0.55,
            glyph_sparkle: 0.24,
          },
        },
      },
    });
    renderPage();

    fireEvent.click(screen.getByRole('button', { name: 'Intense' }));
    fireEvent.click(screen.getByRole('button', { name: 'Compose score + mix' }));

    expect(adaptiveMocks.apiPost).toHaveBeenCalledWith(
      '/api/jarvis/adaptive-music/compose',
      expect.objectContaining({ mood: 'intense', duration_sec: 6, include_mandala_sync: true }),
    );
    expect(await screen.findByText(/arrangement_pcm.v1/)).toBeTruthy();
    expect(screen.getAllByText('mix').length).toBeGreaterThan(0);
    expect(screen.getByTestId('mandala-sync-plan')).toBeTruthy();
    expect(screen.getByTestId('mandala-visual-preview')).toBeTruthy();
    expect(screen.getByText(/mvap_deadbeefcafebabe/)).toBeTruthy();
    expect(screen.getByText(/handheld pulse/)).toBeTruthy();
  });

  it('exposes Sovereign Sound and Voice→Mix panel deep-links', () => {
    renderPage();
    expect(screen.getByRole('link', { name: 'Sovereign Sound' }).getAttribute('href')).toBe(
      '/adaptive-music?panel=sovereign-sound',
    );
    expect(screen.getByRole('link', { name: 'Voice → Mix' }).getAttribute('href')).toBe(
      '/adaptive-music?panel=voice-mix',
    );
    expect(screen.getByRole('link', { name: 'Story Forge Audio' }).getAttribute('href')).toBe(
      '/adaptive-music?panel=story-forge',
    );
  });
});
