import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import Navbar from './Navbar';

vi.mock('../lib/auth', () => ({
  isAmplifyAuthEnabled: () => false,
}));

function renderNav(path = '/jarvis') {
  return render(
    <MemoryRouter initialEntries={[path]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Navbar />
    </MemoryRouter>,
  );
}

describe('Navbar', () => {
  afterEach(() => {
    cleanup();
  });

  it('exposes model library and creative surfaces from the Jarvis shell', () => {
    renderNav('/jarvis');

    expect(screen.getByRole('link', { name: 'Models' }).getAttribute('href')).toBe('/model-library');
    expect(screen.getByRole('link', { name: 'Image' }).getAttribute('href')).toBe('/image-generator');
    expect(screen.getByRole('link', { name: 'Audio' }).getAttribute('href')).toBe('/audio-processor');
    expect(screen.getByRole('link', { name: 'Score' }).getAttribute('href')).toBe('/adaptive-music');
    expect(screen.getByRole('link', { name: 'HoloRT4D' }).getAttribute('href')).toBe('/holo-rt4d');
    expect(screen.getByRole('link', { name: 'Memory Bank' }).getAttribute('href')).toBe('/memory');
  });
});
