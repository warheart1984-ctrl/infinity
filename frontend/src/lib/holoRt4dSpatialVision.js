/** HoloRT4D spatial-vision map helpers for the operator console surface. */

export function buildHoloRt4dConsoleHref({
  spaceId = 'holo_rt4d_demo',
  observer = 'observer',
  tick = 0,
  targets = '',
} = {}) {
  const params = new URLSearchParams();
  if (spaceId) params.set('space_id', String(spaceId));
  if (observer) params.set('observer', String(observer));
  if (tick !== undefined && tick !== null && tick !== '') params.set('tick', String(tick));
  if (targets) params.set('targets', String(targets));
  const query = params.toString();
  return query ? `/holo-rt4d?${query}` : '/holo-rt4d';
}

export function readHoloRt4dSearchParams(search) {
  const params = new URLSearchParams(typeof search === 'string' ? search : '');
  return {
    spaceId: params.get('space_id') || 'holo_rt4d_demo',
    observer: params.get('observer') || 'observer',
    tick: Number.parseInt(params.get('tick') || '0', 10) || 0,
    targets: params.get('targets') || '',
  };
}

export function projectSpatialVisionMap(frame) {
  const viewModel = frame?.view_model;
  if (viewModel && Array.isArray(viewModel.nodes)) {
    return viewModel;
  }
  // Fail soft: empty map when layout is missing.
  return {
    view_box: '0 0 100 100',
    nodes: [],
    entities: [],
    edges: [],
    rays: [],
    cone: null,
    observer: null,
    visible_count: Number(frame?.visible_count) || 0,
    occluded_count: Number(frame?.occluded_count) || 0,
    tick: frame?.tick ?? 0,
    space_id: frame?.space_id || '',
    summary: frame?.summary || '',
  };
}
