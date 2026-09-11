import { readPreferences, savePreferences } from "./preferences.js";
import * as THREE from "../vendor/three.module.js";
export function createScene(host, artwork, onState) {
  const lifetime = new AbortController();
  let stopped = false,
    animationFrame = 0;
  const listen = (target, type, handler) =>
    target.addEventListener(type, handler, { signal: lifetime.signal });
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const pointerCue = document.createElement("span");
  pointerCue.className = "scene-pointer";
  pointerCue.setAttribute("aria-hidden", "true");
  host.append(pointerCue);
  const finePointer = matchMedia("(hover:hover) and (pointer:fine)");
  let pointerCueTimer;
  function movePointerCue(e) {
    if (!finePointer.matches || e.pointerType === "touch") return;
    pointerCue.style.left = e.clientX + "px";
    pointerCue.style.top = e.clientY + "px";
    pointerCue.classList.add("visible");
    const dx = e.movementX || 0,
      dy = e.movementY || 0,
      distance = Math.hypot(dx, dy);
    if (pointer && distance > 0) {
      pointerCue.style.setProperty("--drag-angle", Math.atan2(dy, dx) + "rad");
      pointerCue.style.setProperty(
        "--drag-stretch",
        String(1 + Math.min(distance / 80, 0.22)),
      );
    }
  }
  listen(host, "pointerenter", movePointerCue);
  listen(host, "pointerleave", () => {
    if (!pointer) pointerCue.classList.remove("visible");
  });
  const defaults = {
    speed: 0.55,
    dust: reduced ? 0 : 50,
    softness: 25,
    pixel: reduced ? 0 : 18,
    quality: 1.5,
    fov: 82,
    perspective: 35,
  };
  const ranges = {
    speed: [0.1, 2],
    dust: [0, 100],
    softness: [0, 100],
    pixel: [0, 100],
    quality: [1, 2],
    fov: [65, 125],
    perspective: [0, 60],
  };
  const settings = { auto: !reduced, ...defaults };
  const saved = readPreferences().scene;
  if (saved && typeof saved === "object") {
    for (const [key, [min, max]] of Object.entries(ranges))
      if (Number.isFinite(saved[key]))
        settings[key] = Math.max(min, Math.min(max, saved[key]));
    if (typeof saved.auto === "boolean") settings.auto = saved.auto;
  }
  function saveScene() {
    savePreferences({ scene: { ...settings } });
  }
  let heading = 23,
    pitch = -12,
    goal = 23,
    targetingLandmark = false,
    last = performance.now(),
    pointer = null,
    renderer,
    scene,
    camera,
    panorama,
    dust,
    loaded = false;
  const stateEvent = () =>
    onState({
      heading: ((heading % 360) + 360) % 360,
      auto: settings.auto,
      loaded,
      settings: { ...settings },
    });
  function setSceneSetting(key, value) {
    if (!ranges[key] || !Number.isFinite(value)) return;
    settings[key] = Math.max(ranges[key][0], Math.min(ranges[key][1], value));
    if (key === "quality" && renderer) {
      renderer.setPixelRatio(Math.min(devicePixelRatio, settings.quality));
      renderer.setSize(innerWidth, innerHeight);
    }
    if (key === "fov" && camera) {
      camera.fov = settings.fov;
      camera.updateProjectionMatrix();
    }
    saveScene();
    stateEvent();
  }
  function look(direction) {
    targetingLandmark = direction === "library" || direction === "cave";
    if (direction === "library") goal = 5;
    else if (direction === "cave") goal = 185;
    else goal += direction;
    stateEvent();
  }
  function toggleRotation() {
    settings.auto = !settings.auto;
    goal = heading;
    targetingLandmark = false;
    saveScene();
    stateEvent();
  }
  function resetScene() {
    Object.assign(settings, defaults);
    setSceneSetting("quality", defaults.quality);
    setSceneSetting("fov", defaults.fov);
    saveScene();
    stateEvent();
  }
  const vertex = `varying vec2 vUv; void main(){vUv=uv;gl_Position=vec4(position.xy,1.0,1.0);}`;
  const fragment = `uniform sampler2D uMap;uniform float uSoft;uniform float uPixel;uniform float uTime;uniform float uPerspective;uniform float uAspect;uniform vec2 uCenter;uniform vec2 uSpan;varying vec2 vUv;
// Blend a mild camera-ray projection with the wide illustrated framing.
// Curvature depends only on position in the viewport, never on compass bearing.
// The blend retains the same horizontal bounds and stays inside vertical bounds.
void main(){
vec2 planar=vUv*2.-1.;
float lensX=.72*clamp(uAspect,.7,1.8);
vec2 projected=vec2(atan(planar.x*lensX)/atan(lensX),atan(planar.y*.72,sqrt(1.+pow(planar.x*lensX,2.)))/atan(.72));
vec2 view=mix(planar,projected,uPerspective)*.5;
vec2 uv=vec2(fract(uCenter.x+view.x*uSpan.x),uCenter.y+view.y*uSpan.y);vec4 c=texture2D(uMap,uv);
float horizon=smoothstep(.29,.45,uv.y)*(1.-smoothstep(.57,.70,uv.y));
vec2 s=vec2(.0006,.0004)*uSoft;
vec4 b=(c*4.+texture2D(uMap,uv+s)+texture2D(uMap,uv-s)+texture2D(uMap,uv+vec2(s.x,-s.y))+texture2D(uMap,uv+vec2(-s.x,s.y)))/8.;
c=mix(c,b,horizon*.8);
float accentMask=smoothstep(.04,.08,uv.x)*(1.-smoothstep(.14,.17,uv.x))*smoothstep(.36,.4,uv.y)*(1.-smoothstep(.55,.59,uv.y));
vec2 quant=floor(uv*vec2(340.,170.))/vec2(340.,170.);
c=mix(c,texture2D(uMap,quant),accentMask*uPixel*(.65+.15*sin(uTime*.5)));
float seamBlend=1.-smoothstep(0.,.025,min(uv.x,1.-uv.x));
c=mix(c,(c+texture2D(uMap,vec2(1.-uv.x,uv.y)))*.5,seamBlend);
gl_FragColor=c;
#include <colorspace_fragment>
}`;
  try {
    renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      preserveDrawingBuffer: false,
      powerPreference: "low-power",
    });
    renderer.debug.onShaderError = (gl, program, vs, fs) => {
      host.dataset.renderError = [
        gl.getProgramInfoLog(program),
        gl.getShaderInfoLog(vs),
        gl.getShaderInfoLog(fs),
      ].join("\n");
    };
    renderer.setPixelRatio(Math.min(devicePixelRatio, settings.quality));
    renderer.setSize(innerWidth, innerHeight);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    host.append(renderer.domElement);
    renderer.domElement.setAttribute(
      "aria-label",
      "Rotating library and cave environment",
    );
    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(
      settings.fov,
      innerWidth / innerHeight,
      0.1,
      120,
    );
    const texture = new THREE.TextureLoader().load(
      artwork,
      () => {
        if (stopped) {
          texture.dispose();
          return;
        }
        loaded = true;
        stateEvent();
      },
      undefined,
      () => {
        if (stopped) return;
        host.dataset.mode = "still";
        stateEvent();
      },
    );
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.wrapS = THREE.RepeatWrapping;
    // Wrapped UV derivatives must not select an averaged, orange mip at the join.
    texture.generateMipmaps = false;
    texture.minFilter = THREE.LinearFilter;
    const geometry = new THREE.PlaneGeometry(2, 2);
    panorama = new THREE.Mesh(
      geometry,
      new THREE.ShaderMaterial({
        depthTest: false,
        depthWrite: false,
        uniforms: {
          uMap: { value: texture },
          uSoft: { value: 0.25 },
          uPixel: { value: 0.18 },
          uTime: { value: 0 },
          uPerspective: { value: 0.35 },
          uAspect: { value: camera.aspect },
          uCenter: { value: new THREE.Vector2(0.5, 0.5) },
          uSpan: { value: new THREE.Vector2(0.6, 0.6) },
        },
        vertexShader: vertex,
        fragmentShader: fragment,
      }),
    );
    panorama.frustumCulled = false;
    panorama.renderOrder = -1;
    scene.add(panorama);
    const positions = new Float32Array(180 * 3),
      colors = new Float32Array(180 * 3);
    for (let i = 0; i < 180; i++) {
      const a = Math.random() * Math.PI * 2,
        r = 5 + Math.random() * 19;
      positions[i * 3] = Math.cos(a) * r;
      positions[i * 3 + 1] = (Math.random() - 0.5) * 15;
      positions[i * 3 + 2] = Math.sin(a) * r;
      const tint =
        i % 3 === 0 ? new THREE.Color("#b5e8ff") : new THREE.Color("#e5c885");
      colors[i * 3] = tint.r;
      colors[i * 3 + 1] = tint.g;
      colors[i * 3 + 2] = tint.b;
    }
    const dustGeo = new THREE.BufferGeometry();
    dustGeo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    dustGeo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    dust = new THREE.Points(
      dustGeo,
      new THREE.ShaderMaterial({
        transparent: true,
        depthWrite: false,
        vertexColors: true,
        uniforms: { uOpacity: { value: 0.55 } },
        vertexShader: `varying vec3 vColor;void main(){vColor=color;vec4 p=modelViewMatrix*vec4(position,1.);gl_PointSize=clamp(22./-p.z,1.,5.);gl_Position=projectionMatrix*p;}`,
        fragmentShader: `varying vec3 vColor;uniform float uOpacity;void main(){float d=length(gl_PointCoord-.5);float a=smoothstep(.5,.1,d)*uOpacity;gl_FragColor=vec4(vColor,a);}`,
      }),
    );
    scene.add(dust);
    let frame = 0;
    function animate(now) {
      if (stopped) return;
      animationFrame = requestAnimationFrame(animate);
      if (document.hidden || !loaded) {
        last = now;
        return;
      }
      const delta = Math.min((now - last) / 1000, 0.06);
      last = now;
      const diff = (((goal - heading + 180) % 360) + 360) % 360 - 180;
      heading += diff * Math.min(delta * 2.6, 1);
      // Reach the selected view before automatic drift moves its destination.
      if (targetingLandmark && Math.abs(diff) < 0.05) {
        heading = goal;
        targetingLandmark = false;
        stateEvent();
      } else if (settings.auto && !targetingLandmark) {
        const drift = delta * settings.speed;
        heading += drift;
        goal += drift;
      }
      const yaw = THREE.MathUtils.degToRad(heading),
        p = THREE.MathUtils.degToRad(pitch);
      camera.lookAt(
        Math.sin(yaw) * Math.cos(p),
        Math.sin(p),
        -Math.cos(yaw) * Math.cos(p),
      );
      const artAspect = texture.image
        ? texture.image.width / texture.image.height
        : 2;
      const baseSpanX = Math.min(0.6, (0.9 * camera.aspect) / artAspect);
      const spanX = Math.min(
          (baseSpanX * settings.fov) / 82,
          (0.96 * camera.aspect) / artAspect,
        ),
        spanY = (spanX * artAspect) / camera.aspect;
      panorama.material.uniforms.uCenter.value.set(
        0.5 + heading / 360,
        Math.max(spanY / 2, Math.min(1 - spanY / 2, 0.5 + pitch / 180)),
      );
      panorama.material.uniforms.uSpan.value.set(spanX, spanY);
      panorama.material.uniforms.uPerspective.value = Math.max(
        0,
        Math.min(0.6, settings.perspective / 100),
      );
      panorama.material.uniforms.uAspect.value = camera.aspect;
      panorama.material.uniforms.uSoft.value = settings.softness / 100;
      panorama.material.uniforms.uPixel.value = settings.pixel / 100;
      panorama.material.uniforms.uTime.value = now / 1000;
      dust.visible = settings.dust > 0;
      dust.geometry.setDrawRange(0, Math.round(settings.dust * 1.8));
      dust.material.uniforms.uOpacity.value = 0.4;
      dust.rotation.y = now * 0.000006;
      dust.position.y = Math.sin(now * 0.00013) * 0.2;
      renderer.render(scene, camera);
      host.classList.add("ready");
      if (frame++ % 30 === 0) {
        host.dataset.drawCalls = renderer.info.render.calls;
        host.dataset.loaded = loaded;
        stateEvent();
      }
    }
    animationFrame = requestAnimationFrame(animate);
    listen(window, "resize", () => {
      camera.aspect = innerWidth / innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(innerWidth, innerHeight);
    });
    listen(host, "pointerdown", (e) => {
      if (e.button !== 0) return;
      pointer = { x: e.clientX, y: e.clientY };
      goal = heading;
      targetingLandmark = false;
      clearTimeout(pointerCueTimer);
      pointerCue.classList.remove("released");
      pointerCue.classList.add("dragging");
      host.classList.add("dragging");
      movePointerCue(e);
      host.setPointerCapture(e.pointerId);
      stateEvent();
    });
    listen(host, "pointermove", (e) => {
      movePointerCue(e);
      if (!pointer) return;
      heading -= (e.clientX - pointer.x) * 0.11;
      goal = heading;
      pitch = Math.max(
        -42,
        Math.min(42, pitch + (e.clientY - pointer.y) * 0.08),
      );
      pointer.x = e.clientX;
      pointer.y = e.clientY;
    });
    function releasePointer(e) {
      pointer = null;
      host.classList.remove("dragging");
      pointerCue.classList.remove("dragging");
      pointerCue.classList.add("released");
      pointerCue.style.setProperty("--drag-stretch", "1");
      if (host.hasPointerCapture(e.pointerId))
        host.releasePointerCapture(e.pointerId);
      if (!host.contains(document.elementFromPoint(e.clientX, e.clientY)))
        pointerCue.classList.remove("visible");
      pointerCueTimer = setTimeout(
        () => pointerCue.classList.remove("released"),
        400,
      );
    }
    listen(host, "pointerup", releasePointer);
    listen(host, "pointercancel", releasePointer);
  } catch (error) {
    host.dataset.mode = "still";
    stateEvent();
    console.warn("Scene fallback", error);
  }

  stateEvent();
  return {
    settings,
    look,
    toggleRotation,
    setSceneSetting,
    resetScene,
    dispose() {
      stopped = true;
      cancelAnimationFrame(animationFrame);
      lifetime.abort();
      clearTimeout(pointerCueTimer);
      scene?.traverse((object) => {
        object.geometry?.dispose();
        if (object.material) {
          object.material.uniforms?.uMap?.value?.dispose();
          object.material.dispose();
        }
      });
      renderer?.dispose();
      renderer?.domElement.remove();
      pointerCue.remove();
    },
  };
}
