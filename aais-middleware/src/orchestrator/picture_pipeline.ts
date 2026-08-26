import type { AdapterResult, ParsedPicture } from "../intent_bus/interfaces.js";
import { ImageGenAdapter } from "../provider_adapters/image_gen_adapter.js";
import { MandalaAdapter } from "../provider_adapters/mandala_adapter.js";

export function runImageGenLane(
  pictures: ParsedPicture[],
  opts: { approved: boolean; forceDemo: boolean },
): AdapterResult {
  if (!opts.approved) {
    return {
      provider: "image_gen",
      lane: "picture_generation",
      status: "denied",
      ok: false,
      justification: "Image lane blocked by policy — no silent vendor image API.",
      reasonCode: "TASK_BUS_LANE_DENIED",
    };
  }
  return new ImageGenAdapter({ forceDemo: opts.forceDemo }).generate(pictures);
}

export function runMandalaLane(
  pictures: ParsedPicture[],
  opts: { approved: boolean; forceDemo: boolean },
): AdapterResult {
  if (!opts.approved) {
    return {
      provider: "mandala",
      lane: "mandala_visual",
      status: "denied",
      ok: false,
      justification: "Mandala lane blocked by policy.",
      reasonCode: "TASK_BUS_LANE_DENIED",
    };
  }
  return new MandalaAdapter({ forceDemo: opts.forceDemo }).render(pictures);
}
