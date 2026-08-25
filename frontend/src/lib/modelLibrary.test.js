import { describe, expect, it } from 'vitest';
import { MODEL_LIBRARY_LANES, modelLibraryHref, resolveModelLibraryLane } from './modelLibrary';

describe('FrontierModelLibrarySurface', () => {
  it('maps every catalog modality onto a live operator surface', () => {
    expect(Object.keys(MODEL_LIBRARY_LANES).sort()).toEqual([
      'beatbox',
      'chat',
      'image',
      'img2img',
      'music',
      'voice_stt',
      'voice_tts',
    ]);
    expect(resolveModelLibraryLane('chat')).toEqual({
      to: '/jarvis',
      search: '',
      label: 'Open in Jarvis chat',
      href: '/jarvis',
    });
    expect(modelLibraryHref('img2img')).toBe('/image-generator?mode=img2img');
    expect(modelLibraryHref('voice_stt')).toBe('/audio-processor?lane=stt');
    expect(modelLibraryHref('voice_tts')).toBe('/audio-processor?lane=tts');
    expect(modelLibraryHref('music')).toBe('/audio-processor?lane=music');
    expect(resolveModelLibraryLane('music', 'music.local.beatbox').href).toBe('/adaptive-music');
  });

  it('rejects unknown modalities instead of inventing a route', () => {
    expect(resolveModelLibraryLane('video')).toBeNull();
    expect(modelLibraryHref('')).toBe('');
  });
});
