import { describe, expect, it } from 'vitest';
import {
  buildHoloRt4dConsoleHref,
  projectSpatialVisionMap,
  readHoloRt4dSearchParams,
} from './holoRt4dSpatialVision';

describe('holoRt4dSpatialVision helpers', () => {
  it('builds console hrefs with query params', () => {
    expect(buildHoloRt4dConsoleHref({
      spaceId: 'holo_rt4d_demo',
      observer: 'observer',
      tick: 2,
      targets: 'scout,phantom',
    })).toBe('/holo-rt4d?space_id=holo_rt4d_demo&observer=observer&tick=2&targets=scout%2Cphantom');
  });

  it('reads search params with defaults', () => {
    expect(readHoloRt4dSearchParams('')).toEqual({
      spaceId: 'holo_rt4d_demo',
      observer: 'observer',
      tick: 0,
      targets: '',
    });
    expect(readHoloRt4dSearchParams('tick=3&observer=east')).toEqual({
      spaceId: 'holo_rt4d_demo',
      observer: 'east',
      tick: 3,
      targets: '',
    });
  });

  it('projects an existing view_model passthrough', () => {
    const projected = projectSpatialVisionMap({
      visible_count: 2,
      view_model: { view_box: '0 0 100 100', nodes: [{ id: 'observer' }], rays: [] },
    });
    expect(projected.nodes).toHaveLength(1);
    expect(projected.view_box).toBe('0 0 100 100');
  });
});
