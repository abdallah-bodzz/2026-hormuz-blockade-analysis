/**
 * ambient-field.js
 * ---------------------------------------------------------------------
 * WHAT THIS IS
 * A full-viewport, fixed-position WebGL canvas sitting between the page
 * background and #ambient-glow (the existing five-color CSS radial
 * gradient system that already tracks the reader's phase position).
 * It renders a slow, low-contrast fractal-noise flow field in
 * monochrome and composites onto the page with `mix-blend-mode:
 * soft-light`, so it never introduces its own color — only grain and
 * organic motion that flat CSS gradients can't produce.
 *
 * WHY NOT "REPLACE THE CSS GLOW WITH A HUE-SHIFTING SHADER"
 * That was the brief's suggestion, and it's a reasonable one, but the
 * CSS system already does the color-per-phase job correctly and
 * cheaply (five cross-fading gradients, ~1KB of CSS, GPU-composited for
 * free). Reimplementing that same hue logic in a fragment shader would
 * be duplicated state — two systems that both think they own "what
 * color is the background right now," which is exactly the kind of
 * fight that caused the double hover-treatment bug in the nav pill
 * earlier in this project. Instead this shader is deliberately
 * color-blind: its only job is motion and texture, layered on top of a
 * color system that already works. On phase change it does contribute
 * one small, explicit cue — a soft ripple that expands from center and
 * fades over ~1.8s — as a lightweight nod to "respond to scroll
 * position" without taking over the color signal.
 *
 * PERFORMANCE
 * - Single fullscreen triangle, no scene graph, no lights.
 * - Renders at min(devicePixelRatio, 1.5), not 2 — this canvas covers
 *   the entire viewport (the most expensive one in the file), so pixel
 *   ratio has an outsized cost here specifically.
 * - Render loop is fully stopped (no rAF at all) off-screen — but this
 *   canvas *is* the background, so "off-screen" here means tab hidden,
 *   handled via the visibilitychange listener below, not
 *   IntersectionObserver (which doesn't apply to a fixed fullscreen
 *   element).
 * - Skips mounting entirely under prefers-reduced-motion — an ambient
 *   motion field has no meaning as a static frame, unlike the two
 *   data-scenes, so "reduced" here correctly means "off," not
 *   "slower."
 * ---------------------------------------------------------------------
 */
import * as THREE from 'three';
import { canRenderWebGL, prefersReducedMotion } from './webgl-support.js';

const VERTEX_SHADER = /* glsl */ `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = vec4(position, 1.0);
  }
`;

// Compact 2D simplex noise (Ashima Arts / Stefan Gustavson, public domain)
// plus a 3-octave fbm. Kept intentionally cheap: 3 octaves is enough for
// organic movement at the low contrast this renders at; more would burn
// fill-rate on a fullscreen pass for a difference nobody will see under
// a 6% opacity soft-light blend.
const FRAGMENT_SHADER = /* glsl */ `
  precision mediump float;
  varying vec2 vUv;
  uniform vec2 uResolution;
  uniform float uTime;
  uniform float uRippleStart; // uTime value when the last phase-change ripple fired
  uniform float uRippleMagnitude; // 0..~1.5, scales this ripple's peak intensity
  uniform float uAspect;

  vec3 mod289(vec3 x){return x-floor(x*(1.0/289.0))*289.0;}
  vec2 mod289(vec2 x){return x-floor(x*(1.0/289.0))*289.0;}
  vec3 permute(vec3 x){return mod289(((x*34.0)+1.0)*x);}

  float snoise(vec2 v){
    const vec4 C=vec4(0.211324865405187,0.366025403784439,-0.577350269189626,0.024390243902439);
    vec2 i=floor(v+dot(v,C.yy));
    vec2 x0=v-i+dot(i,C.xx);
    vec2 i1=(x0.x>x0.y)?vec2(1.0,0.0):vec2(0.0,1.0);
    vec4 x12=x0.xyxy+C.xxzz;
    x12.xy-=i1;
    i=mod289(i);
    vec3 p=permute(permute(i.y+vec3(0.0,i1.y,1.0))+i.x+vec3(0.0,i1.x,1.0));
    vec3 m=max(0.5-vec3(dot(x0,x0),dot(x12.xy,x12.xy),dot(x12.zw,x12.zw)),0.0);
    m=m*m; m=m*m;
    vec3 x=2.0*fract(p*C.www)-1.0;
    vec3 h=abs(x)-0.5;
    vec3 ox=floor(x+0.5);
    vec3 a0=x-ox;
    m*=1.79284291400159-0.85373472095314*(a0*a0+h*h);
    vec3 g;
    g.x=a0.x*x0.x+h.x*x0.y;
    g.yz=a0.yz*x12.xz+h.yz*x12.yw;
    return 130.0*dot(m,g);
  }

  float fbm(vec2 p){
    float value=0.0;
    float amp=0.5;
    for(int i=0;i<3;i++){
      value+=amp*snoise(p);
      p*=2.02;
      amp*=0.5;
    }
    return value;
  }

  void main(){
    vec2 uv=vUv;
    vec2 p=vec2(uv.x*uAspect,uv.y);

    // Slow drift — two offset fbm samples advected in different
    // directions so the field doesn't read as a single sliding texture.
    vec2 flowA=p*1.6+vec2(uTime*0.015,-uTime*0.01);
    vec2 flowB=p*2.3+vec2(-uTime*0.008,uTime*0.02);
    float n=fbm(flowA)*0.65+fbm(flowB)*0.35;
    n=n*0.5+0.5; // 0..1

    // Vignette so the effect is strongest near the top (where the hero
    // sits) and fades toward the bottom of the viewport, echoing the
    // existing ambient-glow's own "ellipse at 50% 0%" placement instead
    // of fighting it.
    float vign=1.0-smoothstep(0.0,1.1,length(vec2((uv.x-0.5)*1.4,uv.y-0.05)));
    float field=n*vign;

    // One-shot ripple on phase change: an expanding, fading ring.
    // uRippleMagnitude scales its peak brightness — set per phase by
    // main.js to roughly track the size of that phase's actual market
    // move (e.g. the Shock window's ripple reads stronger than the
    // muted Diplomacy-phase one, echoing the report's own "market
    // learning — the shock is smaller" note). Still color-blind: this
    // only ever changes intensity, never hue.
    float age=uTime-uRippleStart;
    float ripple=0.0;
    if(age>=0.0 && age<1.8){
      float radius=age*0.9;
      float dist=length(vec2((uv.x-0.5)*uAspect,uv.y-0.32));
      float ring=1.0-smoothstep(0.0,0.14,abs(dist-radius));
      ripple=ring*(1.0-age/1.8)*0.5*uRippleMagnitude;
    }

    float lum=clamp(field*0.10+ripple,0.0,1.0);
    gl_FragColor=vec4(vec3(lum),lum);
  }
`;

export function initAmbientField(canvas) {
  if (!canvas || !canRenderWebGL() || prefersReducedMotion()) {
    return null;
  }

  const renderer = new THREE.WebGLRenderer({
    canvas,
    alpha: true,
    antialias: false, // fullscreen post-process style pass; AA is invisible here
    powerPreference: 'low-power',
  });
  renderer.setClearColor(0x000000, 0);
  const pixelRatio = Math.min(window.devicePixelRatio || 1, 1.5);
  renderer.setPixelRatio(pixelRatio);

  const scene = new THREE.Scene();
  const camera = new THREE.Camera(); // fullscreen triangle needs no real projection

  const geometry = new THREE.BufferGeometry();
  // One triangle that overshoots the clip-space square — the standard
  // fullscreen-pass trick, cheaper than a quad (4 verts / 6 indices)
  // because it avoids a diagonal seam and is a single draw call either way.
  geometry.setAttribute(
    'position',
    new THREE.BufferAttribute(new Float32Array([-1, -1, 0, 3, -1, 0, -1, 3, 0]), 3)
  );
  geometry.setAttribute(
    'uv',
    new THREE.BufferAttribute(new Float32Array([0, 0, 2, 0, 0, 2]), 2)
  );

  const uniforms = {
    uResolution: { value: new THREE.Vector2(1, 1) },
    uTime: { value: 0 },
    uRippleStart: { value: -10 },
    uRippleMagnitude: { value: 1 },
    uAspect: { value: 1 },
  };

  const material = new THREE.ShaderMaterial({
    vertexShader: VERTEX_SHADER,
    fragmentShader: FRAGMENT_SHADER,
    uniforms,
    transparent: true,
    depthTest: false,
    depthWrite: false,
  });

  scene.add(new THREE.Mesh(geometry, material));

  const clock = new THREE.Clock();
  let rafId = null;

  function resize() {
    const w = window.innerWidth;
    const h = window.innerHeight;
    renderer.setSize(w, h, false);
    uniforms.uResolution.value.set(w * pixelRatio, h * pixelRatio);
    uniforms.uAspect.value = w / h;
  }

  function tick() {
    uniforms.uTime.value = clock.getElapsedTime();
    renderer.render(scene, camera);
    rafId = requestAnimationFrame(tick);
  }

  function start() {
    if (rafId === null) {
      clock.start();
      tick();
    }
  }
  function stop() {
    if (rafId !== null) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
  }

  resize();
  start();
  window.addEventListener('resize', resize);
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) stop();
    else start();
  });

  return {
    /**
     * Call when the active narrative phase changes to fire the ripple
     * cue. `magnitude` (default 1) scales the ripple's peak intensity —
     * main.js passes a per-phase value roughly tracking that phase's
     * actual market move so the biggest ripple lands on the Shock
     * window, not on whichever phase the reader happens to scroll to.
     */
    pulse(magnitude = 1) {
      uniforms.uRippleStart.value = clock.getElapsedTime();
      uniforms.uRippleMagnitude.value = THREE.MathUtils.clamp(magnitude, 0.4, 1.6);
    },
    dispose() {
      stop();
      window.removeEventListener('resize', resize);
      geometry.dispose();
      material.dispose();
      renderer.dispose();
    },
  };
}