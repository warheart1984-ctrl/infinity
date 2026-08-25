import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import HoloRt4dSpatialVision from './HoloRt4dSpatialVision';

const holoMocks = vi.hoisted(() => ({
  apiPost: vi.fn(),
  getApiErrorMessage: vi.fn((error, fallback) => fallback || error?.message || 'Request failed'),
  toastError: vi.fn(),
}));

vi.mock('../lib/api', () => ({
  apiPost: holoMocks.apiPost,
  getApiErrorMessage: holoMocks.getApiErrorMessage,
}));

vi.mock('react-hot-toast', () => ({
  default: {
    success: vi.fn(),
    error: holoMocks.toastError,
  },
}));

function demoFrame(tick = 0) {
  return {
    type: 'holo_rt4d_spatial_vision',
    space_id: 'holo_rt4d_demo',
    observer: 'observer',
    tick,
    visible_count: tick === 0 ? 5 : 4,
    occluded_count: tick === 0 ? 2 : 3,
    depth_order: ['scout', 'beacon', 'east', 'west', 'south'],
    summary: `HoloRT4D probe at tick ${tick}: demo frame.`,
    console_path: `/holo-rt4d?space_id=holo_rt4d_demo&observer=observer&tick=${tick}`,
    view_model: {
      view_box: '0 0 100 100',
      visible_count: tick === 0 ? 5 : 4,
      occluded_count: tick === 0 ? 2 : 3,
      tick,
      space_id: 'holo_rt4d_demo',
      summary: `HoloRT4D probe at tick ${tick}: demo frame.`,
      observer: { id: 'observer', sx: 50, sy: 50 },
      nodes: [
        { id: 'observer', sx: 50, sy: 50, state: 'observer', kind: 'node' },
        { id: 'east', sx: 80, sy: 50, state: 'visible', kind: 'node' },
        { id: 'north', sx: 50, sy: 20, state: 'occluded', kind: 'node' },
        { id: 'blocker', sx: 50, sy: 35, state: 'obstacle', kind: 'obstacle' },
      ],
      entities: [
        { id: 'scout', sx: 80, sy: 50, state: 'visible', active: true },
        { id: 'phantom', sx: 50, sy: 20, state: tick >= 2 ? 'occluded' : 'inactive', active: tick >= 2 },
      ],
      edges: [{ from: 'observer', to: 'east', x1: 50, y1: 50, x2: 80, y2: 50, obstacle: false }],
      rays: [
        { id: 'scout', visible: true, x1: 50, y1: 50, x2: 80, y2: 50 },
        { id: 'north', visible: false, x1: 50, y1: 50, x2: 50, y2: 20 },
      ],
      cone: { points: '50,50 80,50 50,20', target_count: 1 },
    },
  };
}

function renderPage(path = '/holo-rt4d') {
  return render(
    <MemoryRouter initialEntries={[path]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <HoloRt4dSpatialVision />
    </MemoryRouter>,
  );
}

describe('HoloRt4dSpatialVision', () => {
  beforeEach(() => {
    holoMocks.apiPost.mockReset();
    holoMocks.toastError.mockReset();
    holoMocks.apiPost.mockResolvedValue({ data: demoFrame(0) });
  });

  afterEach(() => {
    cleanup();
  });

  it('loads a probe frame and renders the spatial map readout', async () => {
    renderPage();

    expect(await screen.findByTestId('holo-rt4d-surface')).toBeTruthy();
    await waitFor(() => {
      expect(holoMocks.apiPost).toHaveBeenCalledWith(
        '/api/jarvis/holo-rt4d-spatial-vision/probe',
        expect.objectContaining({
          seed_demo: true,
          include_layout: true,
          observer: 'observer',
        }),
      );
    });
    expect(screen.getByTestId('holo-rt4d-readout').textContent).toMatch(/Visible/);
    expect(screen.getByText(/Depth order/)).toBeTruthy();
    expect(screen.getByRole('img', { name: /Top-down spatial vision map/i })).toBeTruthy();
  });

  it('reprobes when the tick scrubber moves', async () => {
    holoMocks.apiPost
      .mockResolvedValueOnce({ data: demoFrame(0) })
      .mockResolvedValueOnce({ data: demoFrame(2) });
    renderPage('/holo-rt4d?tick=0');

    await screen.findByTestId('holo-rt4d-surface');
    const slider = screen.getByRole('slider', { name: /Tick scrubber/i });
    fireEvent.change(slider, { target: { value: '2' } });

    await waitFor(() => {
      expect(holoMocks.apiPost).toHaveBeenCalledWith(
        '/api/jarvis/holo-rt4d-spatial-vision/probe',
        expect.objectContaining({ tick: 2 }),
      );
    });
  });
});
