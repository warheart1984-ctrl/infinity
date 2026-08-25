import React, { useMemo } from 'react';

/**
 * Mythic: Mandala Visual Preview
 * Engineering: MandalaVisualPreviewSurface
 *
 * Lightweight SVG preview driven by MandalaVisualAdaptationPlan renderer_hooks.
 * Plan-only — not a full shader / Mandala runtime.
 */
function MandalaVisualPreviewSurface({ plan }) {
  const hooks = plan?.renderer_hooks || {};
  const lighting = plan?.lighting || {};
  const glyph = plan?.glyph_particle || {};

  const view = useMemo(() => {
    const intensity = Number(hooks.lighting_intensity ?? lighting.intensity ?? 0.5);
    const hue = Number(hooks.lighting_hue_deg ?? lighting.hue_deg ?? 200);
    const energy = Number(hooks.particle_energy ?? glyph.energy ?? 0.4);
    const density = Number(hooks.particle_density ?? glyph.density ?? 0.35);
    const sparkle = Number(hooks.glyph_sparkle ?? glyph.sparkle ?? 0.2);
    const pulseHz = Number(hooks.camera_pulse_hz ?? plan?.camera?.pulse_hz ?? 1.5);
    const amp = Number(hooks.camera_motion_amplitude ?? plan?.camera?.motion_amplitude ?? 0.4);
    const rings = Math.max(2, Math.min(6, Math.round(2 + density * 4)));
    const petals = Math.max(4, Math.min(16, Math.round(6 + energy * 10)));
    const dots = Math.max(4, Math.min(24, Math.round(4 + sparkle * 20)));

    return {
      intensity,
      hue,
      energy,
      density,
      sparkle,
      pulseHz,
      amp,
      rings,
      petals,
      dots,
      temp: hooks.lighting_temperature || lighting.temperature || 'neutral',
    };
  }, [plan, hooks, lighting, glyph]);

  if (!plan) {
    return null;
  }

  const bg = `hsl(${view.hue} 42% ${18 + view.intensity * 22}%)`;
  const accent = `hsl(${(view.hue + 40) % 360} 70% ${45 + view.sparkle * 20}%)`;
  const ringStroke = `hsla(${view.hue} 65% 70% / ${0.35 + view.energy * 0.45})`;

  return (
    <div
      className="mandala-visual-preview"
      data-testid="mandala-visual-preview"
      style={{ '--mandala-pulse': `${Math.max(0.4, 2 / Math.max(view.pulseHz, 0.2))}s` }}
    >
      <svg viewBox="0 0 200 200" role="img" aria-label="Mandala visual plan preview">
        <rect x="0" y="0" width="200" height="200" fill={bg} rx="12" />
        <g transform="translate(100 100)">
          {Array.from({ length: view.rings }, (_, index) => {
            const radius = 18 + index * (12 + view.amp * 8);
            return (
              <circle
                key={`ring-${index}`}
                r={radius}
                fill="none"
                stroke={ringStroke}
                strokeWidth={1.2 + view.density}
                className="mandala-visual-preview__ring"
              />
            );
          })}
          {Array.from({ length: view.petals }, (_, index) => {
            const angle = (Math.PI * 2 * index) / view.petals;
            const length = 28 + view.energy * 40;
            const x2 = Math.cos(angle) * length;
            const y2 = Math.sin(angle) * length;
            return (
              <line
                key={`petal-${index}`}
                x1="0"
                y1="0"
                x2={x2}
                y2={y2}
                stroke={accent}
                strokeWidth={1.4}
                strokeLinecap="round"
                opacity={0.55 + view.intensity * 0.35}
              />
            );
          })}
          {Array.from({ length: view.dots }, (_, index) => {
            const angle = (Math.PI * 2 * index) / view.dots + view.sparkle;
            const radius = 50 + (index % 3) * 12;
            return (
              <circle
                key={`dot-${index}`}
                cx={Math.cos(angle) * radius}
                cy={Math.sin(angle) * radius}
                r={1.5 + view.sparkle * 2}
                fill={accent}
                className="mandala-visual-preview__spark"
              />
            );
          })}
          <circle r={10 + view.amp * 6} fill={accent} className="mandala-visual-preview__core" />
        </g>
      </svg>
      <p className="file-name">
        preview · {view.temp} · pulse {view.pulseHz.toFixed(2)} Hz · plan-only SVG
      </p>
    </div>
  );
}

export default MandalaVisualPreviewSurface;
