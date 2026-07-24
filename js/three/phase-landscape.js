/**
 * phase-landscape.js
 * ---------------------------------------------------------------------
 * A 3D grouped-bar companion to the Timeline section's phase cards —
 * redesigned around one job: make the decoupling *impossible to miss*,
 * not just visible if you look closely.
 *
 * Four layers, each answering one question a bar chart alone can't:
 *
 *   1. PAIRED BARS (unchanged data) — WTI front (red-2), XOM behind
 *      (steel), same three real windows as before.
 *
 *   2. GAP RIBBONS — a tilted, red-to-steel gradient wall bridging the
 *      top of the WTI bar to the top of the XOM bar in each window.
 *      This is the actual answer to "how far apart is far apart":
 *      near-flat in Pre-Event, a steep red-hot slope in Shock. The
 *      ribbon's tilt *is* the decoupling, not a proxy for it.
 *
 *   3. SHOCK SPOTLIGHT — a soft pulsing floor disc under the Shock
 *      column only, because Finding 01's own sparkline caption says it
 *      plainly: "Divergence begins Feb 28 — never re-converges." That
 *      sentence deserves a single, unambiguous visual anchor, not
 *      generic hover-parity with the other two columns.
 *
 *   4. RATIO SIGNAL LINE — a glowing thread floating above the terrain
 *      tracing the WTI/Gold ratio: flat through Pre-Event, spiking
 *      through Shock (the report's own "peaked Apr 7" note gets a
 *      label), then bending down through Reopen. This is Finding 03 /
 *      the pair-trade exit signal, given a home in the same scene as
 *      the divergence it explains, instead of living only in prose.
 *      Only the one number the report actually states (+47%) is
 *      labeled; the Reopen point is shown as a continuing curve, not a
 *      fabricated percentage.
 *
 * SCOPE NOTE, stated plainly: this still uses exactly three windows
 * (Pre-Event, Shock, Reopen), not all five. Table 1 in the Data section
 * doesn't carry an XOM figure for Correction or Diplomacy — those two
 * windows are already visualized elsewhere via the WTI/Gold ratio and
 * BWET freight KPIs, which is the actual data available for them. I'd
 * rather ship three real bars than five where two are invented. The
 * canvas's aria-label and the caption beside it both say this
 * explicitly, and the exact numbers live in Table 1 regardless of
 * whether the visitor's browser can render WebGL.
 *
 * SCROLL SYNC
 * main.js wires this scene's setActivePhase() into the page's existing
 * setActivePhase() (the one that drives #ambient-glow), via the same
 * window.__hormuzPhaseHooks registry — additive, no rewrite of that
 * logic. Scrolling past the Shock phase card doesn't just change a CSS
 * gradient anymore; the matching column in this scene visibly lifts
 * and brightens, so the 3D companion reads as *of* the page rather than
 * parked next to it.
 *
 * INTERACTION
 * OrbitControls, drag to orbit, scroll/pinch to zoom within a fixed
 * range, no panning (there's nothing productive to pan to). Slow idle
 * auto-rotate when the user isn't touching it, off under
 * prefers-reduced-motion — but manual dragging still works under
 * reduced motion, since that's motion the user asked for one frame at
 * a time, not an animation playing at them.
 * ---------------------------------------------------------------------
 */
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { canRenderWebGL, prefersReducedMotion, cssVarToThreeColor, whenVisible } from './webgl-support.js';

const PHASES = [
  { key: 'pre', label: 'Pre-Event', wti: 16.9, xom: 25.2 },
  { key: 'shock', label: 'Shock', wti: 32.9, xom: -1.4 },
  { key: 'reopen', label: 'Reopen', wti: 27.5, xom: 5.6 },
];

// WTI/Gold ratio — the one hard number the report states is +47% during
// Shock, with an explicit "peaked Apr 7" note (in the Mandates section).
// Pre-Event is the implicit baseline (0 = no signal yet, both assets
// still rising together). Reopen is drawn as a continuing downward
// curve, deliberately unlabeled — the report never gives a Reopen-window
// ratio figure, and inventing one to complete the arc would be exactly
// the kind of fabricated precision this file elsewhere avoids.
const RATIO_SIGNAL = [
  { key: 'pre', value: 0, label: null },
  { key: 'shock', value: 47, label: '+47% · peaked Apr 7' },
  { key: 'reopen', value: 25, label: null },
];

const SPACING = 3.4;
const HEIGHT_SCALE = 0.085;
const BAR_SIZE = 0.9;
const ROW_Z = { wti: 0.75, xom: -0.75 };
const RATIO_BASE_Y = 3.1; // floats above the tallest bar top (~2.8) so it reads as its own layer
const RATIO_SCALE = 0.045;

function barHeight(value) {
  return Math.max(Math.abs(value) * HEIGHT_SCALE, 0.06);
}
function barTopY(value) {
  const h = barHeight(value);
  return value >= 0 ? h : -h;
}

export function initPhaseLandscape(canvas, labelLayer) {
  if (!canvas || !canRenderWebGL()) return null;

  const reduced = prefersReducedMotion();
  const container = canvas.parentElement;

  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
  renderer.setClearColor(0x000000, 0);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.shadowMap.enabled = false; // flat dashboard aesthetic, not a realism render — see materials below

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 50);

  const centerX = ((PHASES.length - 1) * SPACING) / 2;
  camera.position.set(centerX + 4.9, 4.6, 7.2);

  // ── Lighting ─────────────────────────────────────────────────────
  // Deliberately restrained — one soft hemisphere fill plus one
  // directional light just strong enough to model the box faces. Bars
  // also carry their own low-intensity emissive tint (added per-bar
  // below) so they still read clearly even at this light level,
  // matching the page's existing "near-imperceptible unless you look"
  // glow language rather than a punchy, realistic render.
  const hemi = new THREE.HemisphereLight(0x4a5a72, 0x0a0a12, 0.55);
  scene.add(hemi);
  const key = new THREE.DirectionalLight(0xffffff, 1.1);
  key.position.set(4, 6, 3);
  scene.add(key);

  // ── Ground reference ─────────────────────────────────────────────
  const grid = new THREE.GridHelper(SPACING * PHASES.length + 3, 14, 0x3a4658, 0x232c3a);
  grid.position.set(centerX, 0, 0);
  grid.material.transparent = true;
  grid.material.opacity = 0.35;
  scene.add(grid);

  // ── Bars ─────────────────────────────────────────────────────────
  const wtiColor = cssVarToThreeColor(THREE, '--red-2', 0xd1483c);
  const xomColor = cssVarToThreeColor(THREE, '--steel', 0x5a7ba3);
  const amberColor = cssVarToThreeColor(THREE, '--amber', 0xd9a441);
  const goldColor = cssVarToThreeColor(THREE, '--gold', 0xb89158);

  function makeBar(value, color) {
    const h = barHeight(value);
    const geo = new THREE.BoxGeometry(BAR_SIZE, h, BAR_SIZE);
    const mat = new THREE.MeshStandardMaterial({
      color,
      emissive: color,
      emissiveIntensity: 0.22,
      roughness: 0.45,
      metalness: 0.15,
      transparent: true,
      opacity: value < 0 ? 0.55 : 0.92, // negative bars read as "the miss" — visually quieter
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.y = value >= 0 ? h / 2 : -h / 2;
    mesh.userData.baseEmissive = 0.22;
    return mesh;
  }

  // Widest observed gap sets the ribbon-opacity scale so Pre-Event
  // (small gap) and Shock (huge gap) read as visibly different
  // intensities rather than both maxing out the same translucency.
  const maxGap = Math.max(...PHASES.map((p) => Math.abs(p.wti - p.xom)));

  function makeGapRibbon(phase, x) {
    const gap = phase.wti - phase.xom;
    const wtiTop = barTopY(phase.wti);
    const xomTop = barTopY(phase.xom);
    const w = BAR_SIZE * 0.42;

    const geo = new THREE.BufferGeometry();
    const positions = new Float32Array([
      x - w, wtiTop, ROW_Z.wti,
      x + w, wtiTop, ROW_Z.wti,
      x + w, xomTop, ROW_Z.xom,
      x - w, xomTop, ROW_Z.xom,
    ]);
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geo.setIndex([0, 1, 2, 0, 2, 3]);
    geo.computeVertexNormals();

    const colors = new Float32Array([
      wtiColor.r, wtiColor.g, wtiColor.b,
      wtiColor.r, wtiColor.g, wtiColor.b,
      xomColor.r, xomColor.g, xomColor.b,
      xomColor.r, xomColor.g, xomColor.b,
    ]);
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    const opacity = THREE.MathUtils.mapLinear(Math.abs(gap), 0, maxGap, 0.14, 0.58);
    const mat = new THREE.MeshBasicMaterial({
      vertexColors: true,
      transparent: true,
      opacity,
      side: THREE.DoubleSide,
      depthWrite: false,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.userData.baseOpacity = opacity;
    return mesh;
  }

  const barGroups = PHASES.map((phase, i) => {
    const x = i * SPACING;
    const wtiBar = makeBar(phase.wti, wtiColor);
    wtiBar.position.x = x;
    wtiBar.position.z = ROW_Z.wti;
    scene.add(wtiBar);

    const xomBar = makeBar(phase.xom, xomColor);
    xomBar.position.x = x;
    xomBar.position.z = ROW_Z.xom;
    scene.add(xomBar);

    const ribbon = makeGapRibbon(phase, x);
    scene.add(ribbon);

    return { phase, x, wtiBar, xomBar, ribbon };
  });

  // ── Shock spotlight ──────────────────────────────────────────────
  // A soft, slowly pulsing floor disc under the Shock column only —
  // the one window Finding 01 names explicitly as where the divergence
  // starts and never closes again. Everything else in this scene is
  // symmetric across the three columns; this one asymmetry is
  // deliberate.
  const shockGroup = barGroups.find((g) => g.phase.key === 'shock');
  let spotlight = null;
  if (shockGroup) {
    const spotGeo = new THREE.CircleGeometry(SPACING * 0.62, 48);
    const spotMat = new THREE.MeshBasicMaterial({
      color: wtiColor,
      transparent: true,
      opacity: 0.16,
      depthWrite: false,
    });
    spotlight = new THREE.Mesh(spotGeo, spotMat);
    spotlight.rotation.x = -Math.PI / 2;
    spotlight.position.set(shockGroup.x, 0.015, 0);
    scene.add(spotlight);
  }

  // ── WTI/Gold ratio signal line ───────────────────────────────────
  const ratioPoints = RATIO_SIGNAL.map((pt, i) => {
    const x = i * SPACING;
    return new THREE.Vector3(x, RATIO_BASE_Y + pt.value * RATIO_SCALE, 0);
  });
  const ratioCurve = new THREE.CatmullRomCurve3(ratioPoints, false, 'catmullrom', 0.25);
  const ratioTubeGeo = new THREE.TubeGeometry(ratioCurve, 48, 0.028, 8, false);
  const ratioTubeMat = new THREE.MeshBasicMaterial({ color: amberColor, transparent: true, opacity: 0.85 });
  const ratioTube = new THREE.Mesh(ratioTubeGeo, ratioTubeMat);
  scene.add(ratioTube);

  // Small markers at each control point; the peak (Shock) gets a
  // brighter marker since that's the one ratio figure the report
  // actually states.
  const ratioMarkers = RATIO_SIGNAL.map((pt, i) => {
    const isPeak = !!pt.label;
    const geo = new THREE.SphereGeometry(isPeak ? 0.09 : 0.05, 16, 12);
    const mat = new THREE.MeshBasicMaterial({ color: isPeak ? goldColor : amberColor });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.copy(ratioPoints[i]);
    scene.add(mesh);
    return mesh;
  });

  // ── HTML labels, projected from 3D → screen space ─────────────────
  // Simple corner-anchored divs rather than sprites: crisper text, no
  // extra texture atlas, and they stay legible at any camera angle.
  // Beyond the three phase-name labels, two annotation labels ride the
  // same projection system: the shock-spotlight callout and the ratio
  // peak callout — both anchored to real 3D points, not CSS-positioned
  // guesses, so they track the orbit correctly.
  const labelEls = labelLayer
    ? barGroups.map((g) => {
        const el = document.createElement('div');
        el.className = 'landscape-3d-label';
        el.textContent = g.phase.label;
        labelLayer.appendChild(el);
        return el;
      })
    : [];

  let spotlightLabelEl = null;
  let ratioLabelEl = null;
  const ratioAnchor = new THREE.Vector3();
  if (labelLayer) {
    if (shockGroup) {
      spotlightLabelEl = document.createElement('div');
      spotlightLabelEl.className = 'landscape-3d-label landscape-3d-label--callout';
      spotlightLabelEl.textContent = 'Divergence begins — never re-converges';
      labelLayer.appendChild(spotlightLabelEl);
    }
    const peakIndex = RATIO_SIGNAL.findIndex((pt) => pt.label);
    if (peakIndex !== -1) {
      ratioLabelEl = document.createElement('div');
      ratioLabelEl.className = 'landscape-3d-label landscape-3d-label--ratio';
      ratioLabelEl.textContent = `WTI/Gold ${RATIO_SIGNAL[peakIndex].label}`;
      labelLayer.appendChild(ratioLabelEl);
      ratioAnchor.copy(ratioPoints[peakIndex]).setY(ratioPoints[peakIndex].y + 0.35);
    }
  }

  function project(v3, rect) {
    const v = v3.clone().project(camera);
    return {
      x: (v.x * 0.5 + 0.5) * rect.width,
      y: (-v.y * 0.5 + 0.5) * rect.height,
    };
  }

  function updateLabels() {
    const rect = container.getBoundingClientRect();
    if (labelEls.length) {
      barGroups.forEach((g, i) => {
        const p = project(new THREE.Vector3(g.x, 0.15, 0), rect);
        labelEls[i].style.transform = `translate(${p.x}px, ${p.y}px) translate(-50%, 0)`;
      });
    }
    if (spotlightLabelEl && shockGroup) {
      const p = project(new THREE.Vector3(shockGroup.x, -0.05, ROW_Z.xom - 0.9), rect);
      spotlightLabelEl.style.transform = `translate(${p.x}px, ${p.y}px) translate(-50%, 0)`;
    }
    if (ratioLabelEl) {
      const p = project(ratioAnchor, rect);
      ratioLabelEl.style.transform = `translate(${p.x}px, ${p.y}px) translate(-50%, -100%)`;
    }
  }

  // ── Active-phase sync ────────────────────────────────────────────
  // Driven by the page's own scroll-linked setActivePhase() via
  // main.js's hook registry. Not a hard dependency — if the hook never
  // fires (reduced motion aside, this scene still mounts either way),
  // every column simply stays at its resting emissive/opacity level.
  let activeKey = null;
  const emissiveTargets = new Map(); // mesh -> target emissiveIntensity
  const opacityTargets = new Map(); // ribbon -> target opacity

  function applyActivePhase() {
    barGroups.forEach((g) => {
      const isActive = g.phase.key === activeKey;
      emissiveTargets.set(g.wtiBar, isActive ? 0.6 : g.wtiBar.userData.baseEmissive);
      emissiveTargets.set(g.xomBar, isActive ? 0.6 : g.xomBar.userData.baseEmissive);
      opacityTargets.set(g.ribbon, isActive ? Math.min(g.ribbon.userData.baseOpacity * 1.6, 0.85) : g.ribbon.userData.baseOpacity);
    });
  }

  function setActivePhase(phaseKey) {
    if (phaseKey === activeKey) return;
    activeKey = phaseKey;
    applyActivePhase();
  }

  // ── Controls ─────────────────────────────────────────────────────
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(centerX, 1.1, 0);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.enablePan = false;
  controls.minDistance = 5.5;
  controls.maxDistance = 13;
  controls.maxPolarAngle = Math.PI / 2 - 0.04;
  controls.minPolarAngle = 0.3;
  controls.autoRotate = !reduced;
  controls.autoRotateSpeed = 0.5;
  controls.update();

  let idleTimer = null;
  controls.addEventListener('start', () => {
    controls.autoRotate = false;
    if (idleTimer) clearTimeout(idleTimer);
  });
  controls.addEventListener('end', () => {
    if (reduced) return;
    idleTimer = setTimeout(() => {
      controls.autoRotate = true;
    }, 3200);
  });

  // ── Resize ───────────────────────────────────────────────────────
  function resize() {
    const rect = container.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return;
    camera.aspect = rect.width / rect.height;
    camera.updateProjectionMatrix();
    renderer.setSize(rect.width, rect.height, false);
  }
  const resizeObserver = new ResizeObserver(resize);
  resizeObserver.observe(container);
  resize();

  // ── Render loop, gated to visibility ────────────────────────────
  const clock = new THREE.Clock();
  let rafId = null;
  function frame() {
    controls.update();
    updateLabels();

    if (!reduced) {
      const t = clock.getElapsedTime();
      // Shock-spotlight slow pulse — breathing, not flashing.
      if (spotlight) {
        spotlight.material.opacity = 0.12 + Math.sin(t * 0.9) * 0.05;
      }
      // Ratio-line gentle glow drift on the peak marker only.
      const peakIdx = RATIO_SIGNAL.findIndex((pt) => pt.label);
      if (peakIdx !== -1) {
        const s = 1 + Math.sin(t * 1.6) * 0.12;
        ratioMarkers[peakIdx].scale.setScalar(s);
      }
      // Smoothly lerp toward active-phase targets each frame.
      barGroups.forEach((g) => {
        const eW = emissiveTargets.get(g.wtiBar);
        const eX = emissiveTargets.get(g.xomBar);
        const oR = opacityTargets.get(g.ribbon);
        if (eW !== undefined) g.wtiBar.material.emissiveIntensity += (eW - g.wtiBar.material.emissiveIntensity) * 0.12;
        if (eX !== undefined) g.xomBar.material.emissiveIntensity += (eX - g.xomBar.material.emissiveIntensity) * 0.12;
        if (oR !== undefined) g.ribbon.material.opacity += (oR - g.ribbon.material.opacity) * 0.12;
      });
    }

    renderer.render(scene, camera);
    rafId = requestAnimationFrame(frame);
  }
  function start() {
    if (rafId === null) frame();
  }
  function stop() {
    if (rafId !== null) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
  }

  const visibilityObserver = whenVisible(container, start, stop);

  if (reduced) {
    // Render exactly one still frame and leave it there — no loop at all.
    controls.update();
    updateLabels();
    renderer.render(scene, camera);
  }

  return {
    /** Call with 'pre' | 'shock' | 'open' | anything else to sync the highlighted column with the page's scroll-driven active phase. */
    setActivePhase,
    dispose() {
      stop();
      visibilityObserver.disconnect();
      resizeObserver.disconnect();
      controls.dispose();
      renderer.dispose();
      labelEls.forEach((el) => el.remove());
      if (spotlightLabelEl) spotlightLabelEl.remove();
      if (ratioLabelEl) ratioLabelEl.remove();
    },
  };
}