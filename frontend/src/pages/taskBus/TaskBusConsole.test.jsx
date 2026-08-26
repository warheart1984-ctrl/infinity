import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import TaskBusConsole from './TaskBusConsole';

vi.mock('../../lib/api', () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  getApiErrorMessage: (error, fallback = 'Error') => error?.message || fallback,
}));

import { apiGet } from '../../lib/api';

describe('TaskBusConsole', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiGet.mockResolvedValue({
      data: {
        ok: true,
        lanes: [{ provider: 'ms_tasks', label: 'Microsoft Tasks' }],
      },
    });
  });

  it('renders AAIS Middleware Console wireframe panels', async () => {
    render(
      <MemoryRouter>
        <TaskBusConsole />
      </MemoryRouter>,
    );
    expect(await screen.findByRole('heading', { name: /AAIS Middleware Console/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Intent Stream/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Provider Lanes/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Evidence/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Adaptive Engine/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Dispatch/i })).toBeInTheDocument();
  });
});
