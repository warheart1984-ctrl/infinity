/** Mythic: Pictures Lane — Engineering: ImageGenAdapter — AAIS /api/image/generate path */
import type { AdapterResult, ParsedPicture } from "../intent_bus/interfaces.js";

export const AAIS_IMAGE_PATH = "/api/image/generate";

export interface ImageGenConfig {
  forceDemo?: boolean;
  disableDiffusion?: boolean;
}

export class ImageGenAdapter {
  constructor(private readonly config: ImageGenConfig = {}) {}

  generate(pictures: ParsedPicture[]): AdapterResult {
    const frames = pictures.map((p) => ({
      id: p.id,
      prompt: p.target,
      engine: p.engine ?? "aais_image",
      imagePath: AAIS_IMAGE_PATH,
    }));
    return {
      provider: "image_gen",
      lane: "picture_generation",
      status: "demo",
      ok: true,
      justification:
        "AAIS image path planned — Claude/OpenAI do not own pixels here.",
      reasonCode: "TASK_BUS_AAIS_IMAGE_PATH",
      output: {
        imagePath: AAIS_IMAGE_PATH,
        pictures: frames,
        diffusionDisabled: Boolean(this.config.disableDiffusion),
      },
    };
  }
}
