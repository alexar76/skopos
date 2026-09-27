/**
 * SKOPOS hero: the 3D threat globe the product already has in Analytics / Security.
 *
 * Night-ops Earth, GeoIP pins, knock arcs into the fleet watchers (factory / oracle / metis).
 * Procedural — no downloaded textures. Same three.js stack as LOGOS / DOLOS / THEMIS.
 */
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";

const GOLD = 0xffd56a;
const SUN = 0xff8c2a;
const EMBER = 0xe84a1a;
const GOOD = 0x5dffb0;
const CYAN = 0x7b9cff;
const R = 1.62;

const FLEET = [
  { name: "factory", lat: 51.5, lon: -0.12, color: GOLD, orbit: 2.28, phase: 0.12 },
  { name: "oracle", lat: 37.4, lon: -122.1, color: CYAN, orbit: 2.42, phase: 2.18 },
  { name: "metis", lat: 48.86, lon: 2.35, color: GOOD, orbit: 2.35, phase: 4.05 },
];

const PINS = [
  [40.7, -74.0], [35.7, 139.7], [55.75, 37.62], [1.35, 103.8],
  [-33.9, 18.4], [48.85, 2.35], [19.4, -99.1], [-23.55, -46.63],
  [25.2, 55.3], [28.6, 77.2], [59.9, 30.3], [41.9, 12.5],
  [-37.8, 144.9], [37.77, -122.4], [52.5, 13.4],
];

const KNOCKS = [
  { from: [55.75, 37.62], to: 0 },
  { from: [39.9, 116.4], to: 1 },
  { from: [37.57, 126.98], to: 0 },
  { from: [19.07, 72.88], to: 2 },
  { from: [-23.55, -46.63], to: 1 },
  { from: [41.01, 28.98], to: 2 },
  { from: [30.04, 31.24], to: 0 },
  { from: [13.75, 100.5], to: 1 },
  { from: [4.71, -74.07], to: 2 },
  { from: [50.45, 30.52], to: 0 },
];

function latLon(lat, lon, radius) {
  const phi = ((90 - lat) * Math.PI) / 180;
  const theta = ((lon + 180) * Math.PI) / 180;
  return new THREE.Vector3(
    -radius * Math.sin(phi) * Math.cos(theta),
    radius * Math.cos(phi),
    radius * Math.sin(phi) * Math.sin(theta),
  );
}

function makeEarthMaps(w, h) {
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  const ctx = c.getContext("2d");
  const ocean = ctx.createLinearGradient(0, 0, w, 0);
  ocean.addColorStop(0, "#1a0c10");
  ocean.addColorStop(0.45, "#08050c");
  ocean.addColorStop(0.72, "#2a140c");
  ocean.addColorStop(1, "#12080a");
  ctx.fillStyle = ocean;
  ctx.fillRect(0, 0, w, h);

  const land = ctx.createRadialGradient(w * 0.55, h * 0.4, 20, w * 0.55, h * 0.4, w * 0.7);
  land.addColorStop(0, "#c46a28");
  land.addColorStop(1, "#6a3414");
  ctx.fillStyle = land;
  ctx.strokeStyle = "rgba(255, 196, 110, 0.45)";
  ctx.lineWidth = Math.max(1, w / 420);
  const blobs = [
    [0.20, 0.36, 0.15, 0.14, -0.25],
    [0.17, 0.52, 0.07, 0.08, 0.4],
    [0.28, 0.66, 0.09, 0.18, 0.15],
    [0.50, 0.36, 0.10, 0.09, 0.1],
    [0.52, 0.54, 0.11, 0.18, 0.05],
    [0.68, 0.38, 0.20, 0.14, -0.1],
    [0.72, 0.52, 0.12, 0.10, 0.2],
    [0.84, 0.68, 0.09, 0.07, 0.3],
    [0.50, 0.92, 0.42, 0.07, 0],
    [0.58, 0.28, 0.08, 0.05, 0.2],
  ];
  blobs.forEach(([u, v, rx, ry, rot]) => {
    ctx.beginPath();
    ctx.ellipse(u * w, v * h, rx * w, ry * h, rot, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  });

  ctx.fillStyle = "rgba(255, 213, 106, 0.12)";
  blobs.forEach(([u, v, rx, ry, rot]) => {
    ctx.beginPath();
    ctx.ellipse(u * w, v * h, rx * w * 0.55, ry * h * 0.5, rot, 0, Math.PI * 2);
    ctx.fill();
  });

  const map = new THREE.CanvasTexture(c);
  map.colorSpace = THREE.SRGBColorSpace;
  map.anisotropy = 4;

  const e = document.createElement("canvas");
  e.width = w;
  e.height = h;
  const ectx = e.getContext("2d");
  ectx.fillStyle = "#100806";
  ectx.fillRect(0, 0, w, h);
  ectx.fillStyle = "#ffd56a";
  for (let i = 0; i < 900; i++) {
    const x = Math.random() * w;
    const y = Math.random() * h * 0.82 + h * 0.08;
    const inside = blobs.some(([u, v, rx, ry]) => {
      const dx = (x / w - u) / rx;
      const dy = (y / h - v) / ry;
      return dx * dx + dy * dy < 0.85;
    });
    if (!inside || Math.random() > 0.55) continue;
    ectx.globalAlpha = 0.35 + Math.random() * 0.65;
    ectx.beginPath();
    ectx.arc(x, y, Math.random() < 0.08 ? 1.6 : 0.7, 0, Math.PI * 2);
    ectx.fill();
  }
  const emissive = new THREE.CanvasTexture(e);
  emissive.colorSpace = THREE.SRGBColorSpace;
  return { map, emissive };
}

function greatArc(a, b, lift) {
  const mid = a.clone().add(b).multiplyScalar(0.5);
  if (mid.lengthSq() < 1e-6) mid.set(0, 1, 0);
  mid.normalize().multiplyScalar(lift);
  return new THREE.QuadraticBezierCurve3(a, mid, b);
}

export function mountGlobeScene(canvas) {
  const host = canvas.parentElement || canvas;
  const mobile = matchMedia("(max-width: 820px), (pointer: coarse)").matches;
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

  const renderer = new THREE.WebGLRenderer({
    canvas,
    alpha: true,
    antialias: true,
    powerPreference: "high-performance",
  });
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, mobile ? 1.25 : 1.75));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.12;
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 80);
  camera.position.set(0.2, 0.42, 6.35);

  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.055;
  controls.enablePan = false;
  controls.rotateSpeed = 0.48;
  controls.minDistance = 4.6;
  controls.maxDistance = 9.5;
  controls.minPolarAngle = Math.PI * 0.22;
  controls.maxPolarAngle = Math.PI * 0.8;
  controls.autoRotate = !reduced;
  controls.autoRotateSpeed = 0.38;
  controls.target.set(0, 0.05, 0);

  scene.add(new THREE.AmbientLight(0x3a2418, 0.85));
  scene.add(new THREE.HemisphereLight(0xffc888, 0x12080c, 0.55));
  const key = new THREE.PointLight(SUN, 48, 28);
  key.position.set(4.2, 3.4, 5.2);
  scene.add(key);
  const rim = new THREE.PointLight(EMBER, 28, 22);
  rim.position.set(-5, 1.2, -2.4);
  scene.add(rim);
  const fill = new THREE.PointLight(CYAN, 16, 20);
  fill.position.set(-2.4, -3.2, 4);
  scene.add(fill);

  const world = new THREE.Group();
  world.rotation.set(0.18, -0.45, 0.08);
  scene.add(world);

  const tw = mobile ? 512 : 1024;
  const th = mobile ? 256 : 512;
  const { map, emissive } = makeEarthMaps(tw, th);

  const globe = new THREE.Mesh(
    new THREE.SphereGeometry(R, mobile ? 64 : 96, mobile ? 48 : 72),
    new THREE.MeshPhysicalMaterial({
      map,
      emissiveMap: emissive,
      emissive: new THREE.Color(GOLD),
      emissiveIntensity: 1.15,
      roughness: 0.42,
      metalness: 0.22,
      clearcoat: 0.45,
      clearcoatRoughness: 0.4,
    }),
  );
  world.add(globe);

  const atmos = new THREE.Mesh(
    new THREE.SphereGeometry(R * 1.06, 48, 36),
    new THREE.MeshBasicMaterial({
      color: SUN,
      transparent: true,
      opacity: 0.11,
      side: THREE.BackSide,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  world.add(atmos);

  const glow = new THREE.Mesh(
    new THREE.SphereGeometry(R * 1.18, 32, 24),
    new THREE.MeshBasicMaterial({
      color: EMBER,
      transparent: true,
      opacity: 0.06,
      side: THREE.BackSide,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  world.add(glow);

  const wire = new THREE.LineSegments(
    new THREE.WireframeGeometry(new THREE.SphereGeometry(R * 1.002, 28, 16)),
    new THREE.LineBasicMaterial({
      color: 0xffb347,
      transparent: true,
      opacity: 0.07,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  world.add(wire);

  for (const y of [-0.72, 0, 0.72]) {
    const r = Math.sqrt(Math.max(0.05, R * R - y * y));
    const pts = new THREE.EllipseCurve(0, 0, r, r, 0, Math.PI * 2, false, 0)
      .getPoints(96)
      .map((p) => new THREE.Vector3(p.x, y, p.y));
    world.add(
      new THREE.LineLoop(
        new THREE.BufferGeometry().setFromPoints(pts),
        new THREE.LineBasicMaterial({
          color: 0xffc070,
          transparent: true,
          opacity: 0.22,
          blending: THREE.AdditiveBlending,
          depthWrite: false,
        }),
      ),
    );
  }

  const starN = mobile ? 700 : 1600;
  const starPos = new Float32Array(starN * 3);
  const starCol = new Float32Array(starN * 3);
  const pal = [new THREE.Color(GOLD), new THREE.Color(0xfff4e8), new THREE.Color(CYAN), new THREE.Color(SUN)];
  for (let i = 0; i < starN; i++) {
    const r = 14 + Math.random() * 28;
    const tht = Math.random() * Math.PI * 2;
    const ph = Math.acos(2 * Math.random() - 1);
    starPos[i * 3] = r * Math.sin(ph) * Math.cos(tht);
    starPos[i * 3 + 1] = r * Math.sin(ph) * Math.sin(tht);
    starPos[i * 3 + 2] = r * Math.cos(ph);
    const c = pal[(Math.random() * pal.length) | 0];
    starCol.set([c.r, c.g, c.b], i * 3);
  }
  const starsGeo = new THREE.BufferGeometry();
  starsGeo.setAttribute("position", new THREE.BufferAttribute(starPos, 3));
  starsGeo.setAttribute("color", new THREE.BufferAttribute(starCol, 3));
  scene.add(
    new THREE.Points(
      starsGeo,
      new THREE.PointsMaterial({
        size: 0.045,
        vertexColors: true,
        transparent: true,
        opacity: 0.85,
        depthWrite: false,
      }),
    ),
  );

  const pinGeo = new THREE.SphereGeometry(0.028, 10, 10);
  const pinMat = new THREE.MeshBasicMaterial({ color: GOLD });
  const pinHaloMat = new THREE.MeshBasicMaterial({
    color: SUN,
    transparent: true,
    opacity: 0.18,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const pins = [];
  (mobile ? PINS.slice(0, 9) : PINS).forEach(([lat, lon], i) => {
    const p = latLon(lat, lon, R * 1.02);
    const mesh = new THREE.Mesh(pinGeo, pinMat);
    mesh.position.copy(p);
    world.add(mesh);
    const halo = new THREE.Mesh(new THREE.SphereGeometry(0.07, 10, 10), pinHaloMat.clone());
    halo.position.copy(p);
    world.add(halo);
    pins.push({ halo, phase: i * 0.61 });
  });

  const watchers = [];
  FLEET.forEach((f) => {
    const g = new THREE.Group();
    const core = new THREE.Mesh(
      new THREE.OctahedronGeometry(0.11, 0),
      new THREE.MeshStandardMaterial({
        color: f.color,
        emissive: f.color,
        emissiveIntensity: 2.4,
        roughness: 0.2,
        metalness: 0.45,
      }),
    );
    const halo = new THREE.Mesh(
      new THREE.SphereGeometry(0.22, 16, 16),
      new THREE.MeshBasicMaterial({
        color: f.color,
        transparent: true,
        opacity: 0.12,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    );
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(0.26, 0.01, 6, 40),
      new THREE.MeshBasicMaterial({
        color: f.color,
        transparent: true,
        opacity: 0.7,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    );
    ring.rotation.x = Math.PI / 2;
    g.add(core, halo, ring);
    world.add(g);
    watchers.push({ group: g, halo, ring, spec: f });
  });
  function placeWatcher(w, a, y) {
    w.group.position.set(Math.cos(a) * w.spec.orbit, y, Math.sin(a) * w.spec.orbit);
  }
  watchers.forEach((w) => placeWatcher(w, w.spec.phase, 0));

  const routes = [];
  const knockList = mobile ? KNOCKS.slice(0, 6) : KNOCKS;
  knockList.forEach((k, i) => {
    const origin = latLon(k.from[0], k.from[1], R * 1.02);
    const dest = latLon(FLEET[k.to].lat, FLEET[k.to].lon, R * 1.02);
    const lift = R * (1.35 + (i % 3) * 0.08);
    const curve = greatArc(origin, dest, lift);
    const line = new THREE.Mesh(
      new THREE.TubeGeometry(curve, 40, 0.014, 6, false),
      new THREE.MeshBasicMaterial({
        color: i % 2 ? EMBER : SUN,
        transparent: true,
        opacity: 0.55,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    );
    world.add(line);
    const packet = new THREE.Mesh(
      new THREE.SphereGeometry(0.032, 8, 8),
      new THREE.MeshBasicMaterial({
        color: i % 2 ? EMBER : GOLD,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    );
    world.add(packet);
    routes.push({ curve, packet, phase: i / knockList.length, speed: 0.12 + (i % 4) * 0.02 });
  });

  [1.95, 2.22, 2.52].forEach((radius, i) => {
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(radius, 0.008, 8, 180),
      new THREE.MeshBasicMaterial({
        color: [GOLD, SUN, CYAN][i],
        transparent: true,
        opacity: 0.28,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    );
    ring.rotation.set(0.72 + i * 0.18, 0.2 * i, 0.4 - i * 0.12);
    world.add(ring);
  });

  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  if (!mobile) {
    composer.addPass(new UnrealBloomPass(new THREE.Vector2(1, 1), 0.55, 0.62, 0.42));
  }

  function resize() {
    const w = Math.max(1, host.clientWidth);
    const h = Math.max(1, host.clientHeight);
    renderer.setSize(w, h, false);
    composer.setSize(w, h);
    camera.aspect = w / h;
    camera.fov = w / h < 0.9 ? 46 : 38;
    camera.updateProjectionMatrix();
  }
  const ro = new ResizeObserver(resize);
  ro.observe(host);
  resize();

  const clock = new THREE.Clock();
  let alive = true;
  let inView = true;
  let raf = 0;

  canvas.addEventListener("webglcontextlost", (e) => {
    e.preventDefault();
    alive = false;
    cancelAnimationFrame(raf);
    host.classList.add("failed");
  });
  canvas.addEventListener("webglcontextrestored", () => {
    host.classList.remove("failed");
    alive = true;
    kick();
  });

  function frame() {
    if (!alive || !inView) {
      raf = 0;
      return;
    }
    raf = requestAnimationFrame(frame);
    const t = clock.getElapsedTime();
    if (!reduced) {
      globe.rotation.y = t * 0.045;
      wire.rotation.y = -t * 0.02;
      atmos.rotation.y = t * 0.03;
    }
    watchers.forEach((w) => {
      const a = w.spec.phase + t * 0.22;
      const y = Math.sin(a * 1.3) * 0.38;
      placeWatcher(w, a, y);
      const pulse = 1 + Math.sin(t * 2.4 + w.spec.phase) * 0.16;
      w.halo.scale.setScalar(pulse);
      w.ring.rotation.z = t * 0.6 + w.spec.phase;
    });
    pins.forEach((p) => {
      const s = 1 + Math.sin(t * 2.1 + p.phase) * 0.28;
      p.halo.scale.setScalar(s);
      p.halo.material.opacity = 0.12 + Math.sin(t * 2.1 + p.phase) * 0.1;
    });
    if (!reduced) {
      routes.forEach((r) => {
        r.packet.position.copy(r.curve.getPoint((t * r.speed + r.phase) % 1));
      });
    }
    controls.update();
    composer.render();
  }

  function kick() {
    if (!alive || !inView || raf) return;
    raf = requestAnimationFrame(frame);
  }

  if (typeof IntersectionObserver !== "undefined") {
    const io = new IntersectionObserver(
      (entries) => {
        inView = entries.some((e) => e.isIntersecting);
        if (inView) kick();
        else {
          cancelAnimationFrame(raf);
          raf = 0;
        }
      },
      { rootMargin: "40px 0px", threshold: 0.01 },
    );
    io.observe(host);
  }
  kick();

  return {
    dispose() {
      alive = false;
      cancelAnimationFrame(raf);
      ro.disconnect();
    },
  };
}
