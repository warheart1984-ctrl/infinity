import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import OperatorPlugins from './OperatorPlugins';

vi.mock('../lib/api', () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  getApiErrorMessage: (error, fallback = 'Error') => error?.message || fallback,
}));

vi.mock('react-hot-toast', () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));

import { apiGet } from '../lib/api';

function emptyOk(extra = {}) {
  return { data: { ...extra } };
}

describe('OperatorPlugins middleware tab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiGet.mockImplementation(async (url) => {
      if (String(url).includes('middleware/console')) {
        return {
          data: {
            ok: true,
            mode: 'adaptive',
            provider_status: {
              gmail: { connected: false, mode: 'simulate' },
              microsoft: { connected: false, mode: 'simulate' },
              crm: { connected: true, mode: 'live' },
              aais_tasks: { connected: true, mode: 'live' },
              images: { connected: true, mode: 'live' },
            },
            aais_tasks: [],
            recent_requests: [],
          },
        };
      }
      if (String(url).includes('middleware-plugs')) {
        return {
          data: {
            ok: true,
            plugs: [
              {
                plug_id: 'middleware.google.gmail',
                display_name: 'Google Gmail / Email Workflows',
                auth_status: 'needs_auth',
                provider: 'google',
                actions: [{ action_id: 'email_send', label: 'Email send' }],
                activation_hint: 'Set AAIS_GMAIL_ACCESS_TOKEN',
              },
            ],
          },
        };
      }
      if (String(url).includes('/plugins/libraries')) return emptyOk({ libraries: [] });
      if (String(url).includes('/plugins/workflows')) return emptyOk({ workflows: [] });
      if (String(url).includes('/organs/mesh')) return emptyOk({});
      if (String(url).includes('/organs')) return emptyOk({ organs: [] });
      if (String(url).includes('/plugins')) return emptyOk({ plugins: { plugs: [], plug_count: 0, enabled_count: 0 } });
      return emptyOk({ recent_candidates: [] });
    });
  });

  it('shows middleware tab with OperatorMiddlewarePlugRegistry plugs', async () => {
    render(
      <MemoryRouter>
        <OperatorPlugins />
      </MemoryRouter>,
    );
    expect(await screen.findByTestId('middleware-plugs-tab')).toBeTruthy();
    expect(screen.getByText(/OperatorMiddlewarePlugRegistry/i)).toBeTruthy();
    await waitFor(() => {
      expect(screen.getByText(/Google Gmail \/ Email Workflows/i)).toBeTruthy();
    });
    expect(screen.getByRole('button', { name: /Run demo/i })).toBeTruthy();
    expect(screen.getByTestId('connect-gmail')).toBeTruthy();
    expect(screen.getByTestId('aais-tasks-panel')).toBeTruthy();
  });
});
