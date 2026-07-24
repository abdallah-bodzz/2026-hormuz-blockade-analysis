/**
 * main.js — three.js layer entry point
 * ---------------------------------------------------------------------
 * Loaded as a <script type="module"> at the bottom of index.html, after
 * the page's own inline <script>. Module scripts are deferred by spec
 * (execute after the document is parsed, in order), so by the time this
 * runs, every element it queries for already exists and the inline
 * script's own DOM listeners are already attached.
 *
 * This file does three things and nothing else:
 *   1. Feature-gates each scene (WebGL support, container present).
 *   2. Mounts scenes, or shows each one's pre-existing HTML fallback
 *      message if it can't.
 *   3. Hooks BOTH the ambient field's phase-change ripple AND the
 *      phase-landscape's active-column highlight into the page's
 *      existing setActivePhase() logic via a tiny, optional callback
 *      registry (window.__hormuzPhaseHooks) — added as a one-line,
 *      additive change to the inline script (now passing the phase key
 *      through to each hook) rather than this file reaching into and
 *      rewriting that logic itself.
 * ---------------------------------------------------------------------
 */
import { canRenderWebGL, prefersReducedMotion } from './webgl-support.js';
import { initAmbientField } from './ambient-field.js';
import { initPhaseLandscape } from './phase-landscape.js';
import { initAssetGalaxy } from './asset-galaxy.js';

// Ripple magnitude per phase — a rough, deliberately coarse mapping to
// the size of that phase's actual headline move (see Table 1 / the
// phase cards), so the ambient background's one data-adjacent cue
// isn't uniform across phases that were not, in fact, uniform events.
// Diplomacy is muted on purpose: the report's own Finding for that
// phase is "market learning — the shock is smaller."
const RIPPLE_MAGNITUDE = {
  pre: 0.7,
  shock: 1.5,
  open: 1.0,
  correction: 1.15,
  diplomacy: 0.8,
};

// The page's data-phase values (pre / shock / open / correction /
// diplomacy) don't line up 1:1 with the phase-landscape scene's own
// keys — "open" is the page's shorthand for the Reopen phase, while
// the scene's timeline now spans all five phases (pre / shock /
// reopen / correction / diplomacy) rather than just three, so
// correction and diplomacy pass through unchanged.
const LANDSCAPE_KEY = {
  pre: 'pre',
  shock: 'shock',
  open: 'reopen',
  correction: 'correction',
  diplomacy: 'diplomacy',
};

function mountWithFallback(canvasId, fallbackId, mountFn) {
  const canvas = document.getElementById(canvasId);
  const fallback = document.getElementById(fallbackId);
  if (!canvas) return null;

  if (!canRenderWebGL()) {
    canvas.hidden = true;
    if (fallback) fallback.hidden = false;
    return null;
  }

  const instance = mountFn(canvas);
  if (!instance) {
    // mountFn itself declined (e.g. reduced motion, for scenes that
    // opt out entirely rather than degrading — only ambient-field does).
    canvas.hidden = true;
    if (fallback) fallback.hidden = false;
  }
  return instance;
}

document.addEventListener('DOMContentLoaded', () => {
  window.__hormuzPhaseHooks = window.__hormuzPhaseHooks || [];

  // ── Ambient field ──────────────────────────────────────────────
  // No fallback UI needed — this one is purely atmospheric and simply
  // doesn't mount under reduced motion or missing WebGL; the existing
  // CSS #ambient-glow keeps doing its job either way, unaffected.
  const ambientCanvas = document.getElementById('ambient-field-canvas');
  const ambient = ambientCanvas ? initAmbientField(ambientCanvas) : null;
  if (ambient) {
    window.__hormuzPhaseHooks.push((phaseKey) => {
      ambient.pulse(RIPPLE_MAGNITUDE[phaseKey] ?? 1);
    });
  }

  // ── Phase landscape (Timeline) ────────────────────────────────────
  const landscape = mountWithFallback('phase-landscape-canvas', 'phase-landscape-fallback', (canvas) =>
    initPhaseLandscape(canvas, document.getElementById('phase-landscape-labels'))
  );
  if (landscape) {
    window.__hormuzPhaseHooks.push((phaseKey) => {
      landscape.setActivePhase(LANDSCAPE_KEY[phaseKey] ?? null);
    });
  }

  // ── Asset galaxy (Findings) ───────────────────────────────────────
  const galaxy = mountWithFallback('asset-galaxy-canvas', 'asset-galaxy-fallback', (canvas) =>
    initAssetGalaxy(
      canvas,
      document.getElementById('asset-galaxy-tooltip'),
      document.getElementById('asset-galaxy-labels')
    )
  );
  if (galaxy) {
    // Legend regime chips call this global to isolate/clear a regime —
    // additive, same pattern as window.__hormuzPhaseHooks above, so the
    // HTML legend and the in-scene hub click drive identical state.
    window.__hormuzGalaxySetRegime = (regimeKey) => galaxy.setActiveRegime(regimeKey);
  }
});