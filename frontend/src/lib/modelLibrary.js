// Mythic: Model Library
// Engineering: FrontierModelLibrarySurface
//
// Inputs: modality string from GET /api/jarvis/model-library
// Outputs: href + label for the live operator surface
// Constraints: read-only map; does not select or load models
// Failure modes: unknown modality → null (catalog-only, no live surface)

export const MODEL_LIBRARY_LANES = {
  chat: {
    to: '/jarvis',
    search: '',
    label: 'Open in Jarvis chat',
  },
  image: {
    to: '/image-generator',
    search: '?mode=text2img',
    label: 'Open text-to-image',
  },
  img2img: {
    to: '/image-generator',
    search: '?mode=img2img',
    label: 'Open image-to-image',
  },
  voice_stt: {
    to: '/audio-processor',
    search: '?lane=stt',
    label: 'Open transcription',
  },
  voice_tts: {
    to: '/audio-processor',
    search: '?lane=tts',
    label: 'Open speech synthesis',
  },
  music: {
    to: '/audio-processor',
    search: '?lane=music',
    label: 'Open music generator',
  },
  beatbox: {
    to: '/adaptive-music',
    search: '',
    label: 'Open adaptive score',
  },
};

export function resolveModelLibraryLane(modality, entryId) {
  const id = String(entryId || '').trim().toLowerCase();
  if (id.includes('beatbox')) {
    const lane = MODEL_LIBRARY_LANES.beatbox;
    return { ...lane, href: `${lane.to}${lane.search || ''}` };
  }
  const key = String(modality || '').trim().toLowerCase();
  const lane = MODEL_LIBRARY_LANES[key];
  if (!lane) {
    return null;
  }
  return {
    ...lane,
    href: `${lane.to}${lane.search || ''}`,
  };
}

export function modelLibraryHref(modality) {
  return resolveModelLibraryLane(modality)?.href || '';
}
