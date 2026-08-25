import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import TaskBus from './TaskBus';

vi.mock('../lib/api', () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  getApiErrorMessage: (error, fallback = 'Error') => error?.message || fallback,
}));

import { apiGet, apiPost } from '../lib/api';

describe('TaskBus', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiGet.mockResolvedValue({
      data: {
        ok: true,
        lanes: [
          {
            lane_id: 'picture_generation',
            label: 'Picture Generation Lane',
            engineering: 'PictureGenerationLane',
            auth_status: 'demo',
          },
        ],
      },
    });
    apiPost.mockResolvedValue({
      data: {
        ok: true,
        trace_id: 'taskbus_test',
        intent: { kind: 'mixed', requested_lanes: ['picture_generation'] },
        evidence_refs: ['evidence:1'],
        lane_plan: [
          {
            lane_id: 'picture_generation',
            allowed: true,
            reason_code: 'TASK_BUS_LANE_ALLOWED',
            auth_status: 'demo',
          },
        ],
        executions: [
          {
            lane_id: 'picture_generation',
            status: 'completed',
            mode: 'demo',
            reason_code: 'TASK_BUS_AAIS_IMAGE_PATH',
            result: { summary: 'Demo picture', image_path: '/api/image/generate' },
          },
        ],
        decision_events: [],
        replay: { temporal_replay_path: '/operator/replay/task_bus_dispatch/taskbus_test', subject_id: 'taskbus_test' },
      },
    });
  });

  it('renders Task & Skills Bus ingress and lane catalog', async () => {
    render(
      <MemoryRouter>
        <TaskBus />
      </MemoryRouter>,
    );
    expect(await screen.findByRole('heading', { name: /Task & Skills Bus/i })).toBeInTheDocument();
    expect(await screen.findByText(/Picture Generation Lane/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Dispatch/i })).toBeInTheDocument();
  });
});
