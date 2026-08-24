# @mandala/sme

A bounded CommonJS package for the Sovereign Multimodal Engine used by Mandala
and Project Infinity.

## Current maturity

- Package and export contract: **stable-v0**
- Lattice authority, validation, evidence, and replay: **enforced by tests**
- TXT/VIS/AUD/VID/GEN model backends: **experimental** and explicitly initialized
- Jarvis integration: **shadow-only** until behavioral and latency gates pass

The default package has no installed model dependencies and contains no model
weights, native binaries, credentials, runtime logs, or dependency tree.
Optional modality backends must be provided by the host runtime.

## Usage

    const { createLattice } = require('@mandala/sme');

    const runtime = await createLattice({
      modules: new Map([
        ['sme-vis', governedVisionAdapter],
      ]),
    });

    const result = await runtime.call({
      originNodeId: 'sme-core',
      targetNodeId: 'sme-vis',
      actorId: 'jarvis-shadow',
      action: 'classify',
      context: { scope: 'vision-only' },
      payload: { imageData, mimeType: 'image/png' },
    });

Every successful routed operation returns an evidence bundle and replay handle.
A failed authority, validation, or execution check returns a refusal envelope.

## Verification

    npm test
    npm run pack:check

See STABILITY.md for the compatibility contract and PROVENANCE.json for the
source lineage used to establish this package boundary.
