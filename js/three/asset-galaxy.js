/**
 * asset-galaxy.js
 * ---------------------------------------------------------------------
 * A 3D scatter plot companion to the Findings section, redesigned so
 * the *shape* of the fragmentation story is legible without reading a
 * single tooltip. Axes unchanged:
 *   X — Pre-Event return       Y — Shock-window return      Z — Correction-window return
 * Nine real assets, every value pulled directly from Table 1 / Table 2
 * in the Data section further down the page (see DATA below, sourced
 * inline). Where an asset wasn't tracked for a given window, its
 * position on that axis is 0 and the point renders smaller and dimmer
 * on that axis rather than inventing a number — the tooltip says
 * "not tracked this window" rather than showing a fabricated 0.0%.
 *
 * WHAT'S NEW, AND WHY
 *
 *   1. REGIME FLOOR + DROP LINES — every point gets a dashed vertical
 *      line down to a ground plane at Y=0 (Shock return = 0%), ending
 *      in a small disc colored by *regime*, not by individual asset.
 *      This is the fix for "no visual anchor for what far apart
 *      means": the floor plane is a literal, labeled zero-line for the
 *      one axis the report calls its central finding (the Shock
 *      window), and the drop line ties each floating sphere back to it
 *      unambiguously.
 *
 *   2. REGIME HUBS — the report's own "Three Simultaneous Regimes" box
 *      (Scarcity / Stability / Failure) gets a literal home in this
 *      scene: a small marker at the footprint centroid of each group,
 *      with faint spokes connecting every member to its hub. Regime
 *      assignment follows the report's own language (see REGIME_META
 *      and per-asset `regime` below) — Gold and TLT are grouped as
 *      Failure because the report itself names them together as "both
 *      halves of a traditional 60/40 hedge" that broke.
 *
 *   3. "IF CORRELATED" REFERENCE SPHERE — a faint dashed wireframe
 *      sphere at the origin, radius-matched to a ±5% move on every
 *      axis. It operationalizes the caption already sitting next to
 *      this canvas in the HTML ("If the assets clustered here instead
 *      of scattering, that would mean the market treated this as one
 *      story"): now there's an actual "here" to point at, and every
 *      point's visible distance from it *is* the fragmentation.
 *
 * WHY THIS SET OF NINE, NOT "ALL 16"
 * The report's headline is "16 assets, 5 windows," but Table 1 and
 * Table 2 — the only two tables with per-asset numeric returns —
 * between them name nine: WTI, S&P 500, Gold, XOM, JETS, ITA, BWET,
 * TLT, CVX. The other seven exist in the underlying dataset (visible
 * in the correlation matrix and seasonal tables) but aren't broken out
 * as individual return figures anywhere on this page, so there's
 * nothing to plot for them without guessing. Nine real points beat
 * sixteen where seven are made up.
 *
 * Point size encodes Shock Vol% where it's known (a fourth dimension
 * for free) — this is *also* why WTI, the highest-volatility asset in
 * the set at 98.5%, reads as visibly the largest sphere even before
 * you check its position.
 *
 * SOURCE OF TRUTH STAYS THE TABLE
 * This scene has no keyboard interaction and can't be operated by a
 * screen reader — that's a real, permanent limitation of hover-driven
 * WebGL raycasting, not something worth pretending to solve with a
 * token tabindex loop that wouldn't actually convey 3D spatial
 * relationships anyway. The identical nine values are already in
 * Table 1/2 as normal HTML, which is why this canvas's aria-label
 * says exactly that, and why nothing here is the only place a number
 * appears.
 * ---------------------------------------------------------------------
 */
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { canRenderWebGL, prefersReducedMotion, resolveCssColor, whenVisible } from './webgl-support.js';

// pre / shock / correction are % returns, null = not tracked that window.
// vol = shock-window realized volatility %, null = not reported.
//
// `regime` follows the report's own "Market Fragmentation: Three
// Simultaneous Regimes" box in the Findings section:
//   scarcity   — "Regime A: Scarcity — Physical Commodity" (WTI named explicitly;
//                 BWET/freight added here as the other physical, non-financial
//                 asset in the set — a reasonable extension of the same
//                 category, not a claim the report itself makes verbatim)
//   stability  — "Regime B: Stability — Equity Market" (S&P 500 named
//                 explicitly; XOM/CVX/JETS/ITA are equities in the same
//                 market, grouped consistent with Finding 01's point that
//                 energy equities decoupled from oil and behaved like equities)
//   failure    — "Regime C: Failure — Safe Havens" (Gold AND TLT are named
//                 together in that box as "both halves of a traditional
//                 60/40 hedge" that underperformed)
const ASSETS = [
  { name: 'WTI Crude',    cls: 'Energy — Physical', regime: 'scarcity',  pre: 16.9, shock: 32.9,  corr: -20,  vol: 98.5, color: 'oklch(52% 0.20 27)' },
  { name: 'S&P 500',      cls: 'Equity Index',       regime: 'stability', pre: 0.3,  shock: 2.3,   corr: null, vol: 17.5, color: 'oklch(65% 0.12 175)' },
  { name: 'Gold',         cls: 'Safe Haven',         regime: 'failure',   pre: 21.2, shock: -9.6,  corr: null, vol: 34.0, color: 'oklch(72% 0.10 85)' },
  { name: 'Exxon (XOM)',  cls: 'Energy — Equity',    regime: 'stability', pre: 25.2, shock: -1.4,  corr: null, vol: 29.2, color: 'oklch(52% 0.10 240)' },
  { name: 'Airlines (JETS)', cls: 'Equity — Sector', regime: 'stability', pre: 0.6,  shock: -3.9,  corr: null, vol: 38.1, color: 'oklch(58% 0.08 270)' },
  { name: 'Defense (ITA)',   cls: 'Equity — Sector', regime: 'stability', pre: null, shock: 5.5,   corr: 8.9,  vol: null, color: 'oklch(55% 0.12 290)' },
  { name: 'Freight (BWET)',  cls: 'Shipping',        regime: 'scarcity',  pre: null, shock: 71.1,  corr: null, vol: null, color: 'oklch(62% 0.11 200)' },
  { name: 'LT Bonds (TLT)',  cls: 'Fixed Income',     regime: 'failure',   pre: null, shock: -3.3,  corr: null, vol: null, color: 'oklch(50% 0.08 160)' },
  // No existing dot-color token for CVX in the stylesheet (it only
  // appears in Table 2, not the asset-dot legend); chosen in the same
  // blue family as XOM since both are oil-equity, not oil-physical.
  { name: 'Chevron (CVX)',   cls: 'Energy — Equity', regime: 'stability', pre: null, shock: -0.8,  corr: null, vol: null, color: 'oklch(58% 0.09 235)' },
];

const REGIME_META = {
  scarcity:  { label: 'Scarcity — Physical Commodity', varName: '--red-2' },
  stability: { label: 'Stability — Equity Market',      varName: '--t2' },
  failure:   { label: 'Failure — Safe Havens',           varName: '--gold' },
};

const AXIS_SCALE = 0.9; // applied after sqrt-compression, see posFor()

function posFor(value) {
  if (value === null || value === undefined) return 0;
  return Math.sign(value) * Math.sqrt(Math.abs(value)) * AXIS_SCALE;
}

function sizeFor(vol) {
  if (vol === null || vol === undefined) return 0.15;
  return THREE.MathUtils.mapLinear(THREE.MathUtils.clamp(vol, 15, 100), 15, 100, 0.13, 0.34);
}

export function initAssetGalaxy(canvas, tooltipEl, labelLayer) {
  if (!canvas || !canRenderWebGL()) return null;

  const reduced = prefersReducedMotion();
  const container = canvas.parentElement;

  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
  renderer.setClearColor(0x000000, 0);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 60);
  camera.position.set(9, 6, 10);

  const hemi = new THREE.HemisphereLight(0x4a5a72, 0x0a0a12, 0.6);
  scene.add(hemi);
  const key = new THREE.DirectionalLight(0xffffff, 1.0);
  key.position.set(5, 8, 4);
  scene.add(key);

  // ── Axis guides ──────────────────────────────────────────────────
  // Thin dashed lines through the origin rather than in-scene text —
  // text sprites are blurry at this scale and rotate awkwardly with
  // the camera; the HTML legend beside the canvas carries the actual
  // axis labels and stays crisp at any orbit angle.
  const axisColorX = resolveCssColor(THREE, 'var(--t3)', 0x8a8f9a);
  const axisColorY = resolveCssColor(THREE, 'var(--red-2)', 0xd1483c);
  const axisColorZ = resolveCssColor(THREE, 'var(--amber)', 0xd9a441);
  const AXIS_LEN = 8.5;
  function axisLine(dir, color) {
    const points = [dir.clone().multiplyScalar(-AXIS_LEN), dir.clone().multiplyScalar(AXIS_LEN)];
    const geo = new THREE.BufferGeometry().setFromPoints(points);
    const mat = new THREE.LineDashedMaterial({ color, dashSize: 0.22, gapSize: 0.16, transparent: true, opacity: 0.3 });
    const line = new THREE.Line(geo, mat);
    line.computeLineDistances();
    return line;
  }
  scene.add(axisLine(new THREE.Vector3(1, 0, 0), axisColorX));
  scene.add(axisLine(new THREE.Vector3(0, 1, 0), axisColorY));
  scene.add(axisLine(new THREE.Vector3(0, 0, 1), axisColorZ));

  // ── Asset points ─────────────────────────────────────────────────
  const meshes = [];
  ASSETS.forEach((asset) => {
    const color = resolveCssColor(THREE, asset.color, 0x888888);
    const r = sizeFor(asset.vol);
    const geo = new THREE.SphereGeometry(r, 20, 16);
    const hasAllAxes = asset.pre !== null && asset.corr !== null;
    const mat = new THREE.MeshStandardMaterial({
      color,
      emissive: color,
      emissiveIntensity: 0.35,
      roughness: 0.35,
      metalness: 0.2,
      transparent: true,
      opacity: hasAllAxes ? 0.95 : 0.65, // partial-data points sit back visually, on purpose
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.set(posFor(asset.pre), posFor(asset.shock), posFor(asset.corr));
    mesh.userData.asset = asset;
    scene.add(mesh);
    meshes.push(mesh);
  });

  // ── Zero-return floor (Y=0, the Shock-window baseline) ────────────
  // The report calls the Shock window the central finding, so the axis
  // that most needs a visible zero-line is Y, not the ground plane a
  // generic 3D scatter would default to (which is usually just "down").
  // A literal grid here — not a color, not a caption — is the fix for
  // "no visual anchor for what far apart means."
  const floorSize = AXIS_LEN * 1.5;
  const floorGrid = new THREE.GridHelper(floorSize, 16, 0x3a4658, 0x232c3a);
  floorGrid.material.transparent = true;
  floorGrid.material.opacity = 0.22;
  scene.add(floorGrid);

  // ── Regime colors, resolved once ──────────────────────────────────
  const regimeColors = {};
  Object.entries(REGIME_META).forEach(([key, meta]) => {
    regimeColors[key] = resolveCssColor(THREE, `var(${meta.varName})`, 0x888888);
  });

  // ── Drop lines + regime-coded footprints ──────────────────────────
  // Every sphere gets a dashed vertical line straight down to the
  // Y=0 floor, ending in a small flat disc. The disc is colored by
  // *regime*, not by the asset's own color — this is the layer that
  // answers "which of the three simultaneous regimes was this asset
  // in" without needing a tooltip.
  const footprints = meshes.map((mesh) => {
    const asset = mesh.userData.asset;
    const regimeColor = regimeColors[asset.regime];
    const foot = new THREE.Vector3(mesh.position.x, 0, mesh.position.z);

    const dropGeo = new THREE.BufferGeometry().setFromPoints([mesh.position.clone(), foot.clone()]);
    const dropMat = new THREE.LineDashedMaterial({
      color: regimeColor,
      dashSize: 0.1,
      gapSize: 0.08,
      transparent: true,
      opacity: 0.4,
    });
    const dropLine = new THREE.Line(dropGeo, dropMat);
    dropLine.computeLineDistances();
    scene.add(dropLine);

    const dotGeo = new THREE.CircleGeometry(0.09, 20);
    const dotMat = new THREE.MeshBasicMaterial({ color: regimeColor, transparent: true, opacity: 0.85 });
    const dot = new THREE.Mesh(dotGeo, dotMat);
    dot.rotation.x = -Math.PI / 2;
    dot.position.copy(foot);
    dot.position.y = 0.008;
    scene.add(dot);

    return { asset, point: foot };
  });

  // ── Regime hubs + spokes ───────────────────────────────────────────
  // One marker per regime, placed at the centroid of its members'
  // footprints, with a faint spoke line from every member to its hub.
  // This is the "Three Simultaneous Regimes" fragmentation box from
  // the Findings section, made spatial: three visibly separated hubs
  // instead of one cluster is the same claim the report makes in prose.
  const hubLabelEls = [];
  const hubAnchors = [];
  Object.keys(REGIME_META).forEach((regimeKey) => {
    const members = footprints.filter((f) => f.asset.regime === regimeKey);
    if (!members.length) return;
    const centroid = new THREE.Vector3();
    members.forEach((m) => centroid.add(m.point));
    centroid.divideScalar(members.length);

    const color = regimeColors[regimeKey];
    const hubGeo = new THREE.OctahedronGeometry(0.16, 0);
    const hubMat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.9 });
    const hub = new THREE.Mesh(hubGeo, hubMat);
    hub.position.copy(centroid);
    hub.position.y = 0.02;
    scene.add(hub);

    members.forEach((m) => {
      const spokeGeo = new THREE.BufferGeometry().setFromPoints([m.point, centroid]);
      const spokeMat = new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.28 });
      scene.add(new THREE.Line(spokeGeo, spokeMat));
    });

    if (labelLayer) {
      const el = document.createElement('div');
      el.className = 'landscape-3d-label galaxy-3d-regime-label';
      el.textContent = REGIME_META[regimeKey].label;
      el.style.setProperty('--regime-color', `#${color.getHexString()}`);
      labelLayer.appendChild(el);
      hubLabelEls.push(el);
      hubAnchors.push(new THREE.Vector3(centroid.x, 0.35, centroid.z));
    }
  });

  // ── "If correlated" reference sphere ───────────────────────────────
  // A faint dashed wireframe icosphere at the origin, radius-matched to
  // a ±5% move on every axis. It gives the caption already sitting next
  // to this canvas ("if the assets clustered here instead of
  // scattering...") an actual "here" — every point's visible distance
  // outside this sphere is the fragmentation the report describes.
  const refRadius = posFor(5);
  const refGeo = new THREE.IcosahedronGeometry(refRadius, 1);
  const refWire = new THREE.WireframeGeometry(refGeo);
  const refMat = new THREE.LineBasicMaterial({
    color: resolveCssColor(THREE, 'var(--t3)', 0x8a8f9a),
    transparent: true,
    opacity: 0.22,
  });
  const refSphere = new THREE.LineSegments(refWire, refMat);
  scene.add(refSphere);

  let refLabelEl = null;
  if (labelLayer) {
    refLabelEl = document.createElement('div');
    refLabelEl.className = 'landscape-3d-label landscape-3d-label--callout';
    refLabelEl.textContent = 'If correlated: everything stays in here';
    labelLayer.appendChild(refLabelEl);
  }
  const refLabelAnchor = new THREE.Vector3(refRadius * 0.75, refRadius * 0.75, refRadius * 0.75);

  // ── Controls ─────────────────────────────────────────────────────
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(0, 0.5, 0);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.enablePan = false;
  controls.minDistance = 6;
  controls.maxDistance = 20;
  controls.autoRotate = !reduced;
  controls.autoRotateSpeed = 0.4;
  controls.update();

  let idleTimer = null;
  controls.addEventListener('start', () => {
    controls.autoRotate = false;
    if (idleTimer) clearTimeout(idleTimer);
  });
  controls.addEventListener('end', () => {
    if (reduced) return;
    idleTimer = setTimeout(() => (controls.autoRotate = true), 3500);
  });

  // ── Hover / tap raycasting ───────────────────────────────────────
  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  let hovered = null;

  function pointFromEvent(event) {
    const rect = canvas.getBoundingClientRect();
    const x = (event.clientX ?? event.touches?.[0]?.clientX) - rect.left;
    const y = (event.clientY ?? event.touches?.[0]?.clientY) - rect.top;
    pointer.x = (x / rect.width) * 2 - 1;
    pointer.y = -(y / rect.height) * 2 + 1;
    return { x, y };
  }

  function fmtPct(v) {
    if (v === null || v === undefined) return 'not tracked this window';
    const sign = v > 0 ? '+' : '';
    return `${sign}${v.toFixed(1)}%`;
  }

  function showTooltip(mesh, screenPos) {
    if (!tooltipEl) return;
    const a = mesh.userData.asset;
    const regime = REGIME_META[a.regime];
    tooltipEl.innerHTML =
      `<strong>${a.name}</strong>` +
      `<span class="galaxy-tooltip-cls">${a.cls}</span>` +
      `<span>Pre-Event: ${fmtPct(a.pre)}</span>` +
      `<span>Shock: ${fmtPct(a.shock)}</span>` +
      `<span>Correction: ${fmtPct(a.corr)}</span>` +
      (regime ? `<span class="galaxy-tooltip-regime" style="--regime-color:#${regimeColors[a.regime].getHexString()}">${regime.label}</span>` : '');
    tooltipEl.style.left = `${screenPos.x}px`;
    tooltipEl.style.top = `${screenPos.y}px`;
    tooltipEl.classList.add('is-visible');
  }
  function hideTooltip() {
    if (tooltipEl) tooltipEl.classList.remove('is-visible');
    hovered = null;
  }

  function handlePointer(event) {
    const screenPos = pointFromEvent(event);
    raycaster.setFromCamera(pointer, camera);
    const hits = raycaster.intersectObjects(meshes);
    if (hits.length) {
      hovered = hits[0].object;
      showTooltip(hovered, screenPos);
    } else if (event.type !== 'pointerdown') {
      hideTooltip();
    }
  }
  canvas.addEventListener('pointermove', handlePointer);
  canvas.addEventListener('pointerdown', handlePointer);
  canvas.addEventListener('pointerleave', hideTooltip);

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

  // ── HTML label projection (regime hubs + reference sphere) ───────
  function projectLabel(v3, rect) {
    const v = v3.clone().project(camera);
    return {
      x: (v.x * 0.5 + 0.5) * rect.width,
      y: (-v.y * 0.5 + 0.5) * rect.height,
    };
  }
  function updateLabels() {
    if (!hubLabelEls.length && !refLabelEl) return;
    const rect = container.getBoundingClientRect();
    hubLabelEls.forEach((el, i) => {
      const p = projectLabel(hubAnchors[i], rect);
      el.style.transform = `translate(${p.x}px, ${p.y}px) translate(-50%, -100%)`;
    });
    if (refLabelEl) {
      const p = projectLabel(refLabelAnchor, rect);
      refLabelEl.style.transform = `translate(${p.x}px, ${p.y}px) translate(-50%, 0)`;
    }
  }

  // ── Render loop, gated to visibility ────────────────────────────
  const clock = new THREE.Clock();
  let rafId = null;
  function frame() {
    controls.update();
    updateLabels();
    // Gentle pulse on the hovered sphere only — cheap, and confirms
    // the raycast hit landed on the object the tooltip is describing.
    meshes.forEach((m) => {
      const targetScale = m === hovered ? 1.25 : 1.0;
      m.scale.lerp(new THREE.Vector3(targetScale, targetScale, targetScale), 0.2);
    });
    // Reference sphere gets a near-imperceptible slow rotation so it
    // still reads as "a sphere" rather than a flat wireframe circle
    // from certain angles — the only motion in this scene that isn't
    // orbit-driven or hover-driven, so it stays off under reduced motion.
    if (!reduced) {
      const t = clock.getElapsedTime();
      refSphere.rotation.y = t * 0.05;
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
    controls.update();
    updateLabels();
    renderer.render(scene, camera);
  }

  return {
    dispose() {
      stop();
      visibilityObserver.disconnect();
      resizeObserver.disconnect();
      controls.dispose();
      renderer.dispose();
      canvas.removeEventListener('pointermove', handlePointer);
      canvas.removeEventListener('pointerdown', handlePointer);
      canvas.removeEventListener('pointerleave', hideTooltip);
      hubLabelEls.forEach((el) => el.remove());
      if (refLabelEl) refLabelEl.remove();
    },
  };
}