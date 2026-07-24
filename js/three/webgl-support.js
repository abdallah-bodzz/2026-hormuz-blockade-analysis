/**
 * webgl-support.js
 * ---------------------------------------------------------------------
 * Shared gate used by every scene in js/three/. Two independent checks:
 *
 *   1. canRenderWebGL() — is there a real, working WebGL2/WebGL context?
 *      Cheap, synchronous, throwaway canvas — the standard feature test.
 *
 *   2. prefersReducedMotion() — re-checked live (not cached at module
 *      load) since a user can flip the OS setting while the tab is open
 *      and some browsers fire a change event for it.
 *
 * Callers combine these with their own judgment: a scene that has a
 * meaningful *static* frame (the phase landscape, the asset galaxy) can
 * still mount under reduced motion — it just skips OrbitControls'
 * damping/idle-rotate and renders a single still frame instead of a
 * loop. A scene that has no meaning without motion (the ambient field)
 * should just not mount at all. Each scene file makes that call itself;
 * this module only reports the facts.
 *
 * Also exports `whenVisible()`, an IntersectionObserver wrapper every
 * scene uses to start/stop its render loop. The report is long and
 * text-heavy — a 3D scene animating at 60fps two thousand pixels below
 * the fold is pure waste, and on a busy page it's the difference
 * between smooth scrolling and janky scrolling. Nothing in this repo
 * runs a render loop while its container is off-screen.
 * ---------------------------------------------------------------------
 */

export function canRenderWebGL() {
  try {
    const canvas = document.createElement('canvas');
    const gl =
      canvas.getContext('webgl2') ||
      canvas.getContext('webgl') ||
      canvas.getContext('experimental-webgl');
    if (!gl) return false;
    // A context can exist but be software-rendered/blocklisted on some
    // locked-down browsers; that's still "works," just slow, and three
    // small scenes on a static page won't notice. Not worth filtering.
    return true;
  } catch (e) {
    return false;
  }
}

export function prefersReducedMotion() {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

export function isFinePointer() {
  return window.matchMedia('(hover: hover) and (pointer: fine)').matches;
}

/**
 * Runs `onEnter` when `el` scrolls into view and `onExit` when it
 * scrolls out, with a small rootMargin so the render loop spins up
 * slightly before the element is actually visible (avoids a blank
 * flash) and tears down slightly after it leaves (avoids thrash on
 * fast scroll near the boundary).
 */
export function whenVisible(el, onEnter, onExit) {
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) onEnter();
        else onExit();
      });
    },
    { rootMargin: '200px 0px 200px 0px', threshold: 0.01 }
  );
  observer.observe(el);
  return observer;
}

/**
 * Resolves *any* CSS color string — a var() reference, a literal
 * oklch()/hsl()/hex, whatever — down to concrete sRGB bytes, and hands
 * back a THREE.Color.
 *
 * WHY THIS ISN'T getComputedStyle(el).color (a real bug fixed here)
 * The original version of this function read `color` back off a probe
 * element via getComputedStyle, on the assumption that computed style
 * always normalizes to rgb()/rgba(). That assumption broke on current
 * Chrome: per the CSS Color 4 spec, a browser is allowed to preserve
 * the *specified* color space in computed style rather than always
 * down-converting to sRGB, and Chrome does exactly that for oklch().
 * On a page whose entire palette is written in oklch(), that meant
 * getComputedStyle(...).color could itself hand back an oklch() string
 * — which THREE.Color.setStyle() doesn't parse, and threw "Unknown
 * color model" for every single swatch (visible as the flat gray
 * fallback the bars and spheres were rendering in).
 *
 * A <canvas> 2D context's fillStyle goes through the same full CSS
 * color parser (oklch included), but reading the pixel back with
 * getImageData() is *guaranteed* to return concrete 0–255 sRGB bytes —
 * there's no color space left for a browser to preserve once it's
 * pixels. That guarantee, not any assumption about a specific
 * browser's serialization behavior, is why this is the correct tool.
 *
 * var() references are resolved first via getPropertyValue() on the
 * document root, which returns the custom property's literal source
 * text (e.g. "oklch(52% 0.2 27)") completely unaffected by the
 * computed-color-serialization behavior above, since custom properties
 * are returned verbatim rather than recomputed through the color
 * pipeline.
 */
let _colorProbeCtx = null;
function colorProbeContext() {
  if (!_colorProbeCtx) {
    const canvas = document.createElement('canvas');
    canvas.width = 1;
    canvas.height = 1;
    _colorProbeCtx = canvas.getContext('2d', { willReadFrequently: true });
  }
  return _colorProbeCtx;
}

export function resolveCssColor(THREE, cssColorString, fallbackHex = 0x888888) {
  let literal = String(cssColorString).trim();
  const varMatch = literal.match(/^var\((--[\w-]+)\)$/);
  if (varMatch) {
    const propValue = getComputedStyle(document.documentElement).getPropertyValue(varMatch[1]);
    if (propValue && propValue.trim()) literal = propValue.trim();
  }

  try {
    const ctx = colorProbeContext();
    // Reset to a known, unmistakable value first — an invalid `literal`
    // makes canvas silently *keep the previous fillStyle* rather than
    // throw, so without this reset a bad color string would read back
    // as whatever the last successfully-resolved color happened to be.
    ctx.fillStyle = '#ff00ff';
    ctx.fillStyle = literal;
    ctx.fillRect(0, 0, 1, 1);
    const [r, g, b] = ctx.getImageData(0, 0, 1, 1).data;
    const color = new THREE.Color();
    color.setStyle(`rgb(${r}, ${g}, ${b})`);
    return color;
  } catch (e) {
    return new THREE.Color(fallbackHex);
  }
}

export function cssVarToThreeColor(THREE, varName, fallbackHex = 0x888888) {
  return resolveCssColor(THREE, `var(${varName})`, fallbackHex);
}