import * as THREE from "three";

/** View-only contours. Borrowed asset geometry/textures are never modified or disposed. */
export class AssetOutlineRenderer {
  private readonly mask = new THREE.WebGLRenderTarget(1, 1, {
    minFilter: THREE.NearestFilter,
    magFilter: THREE.NearestFilter,
  });
  private readonly maskScene = new THREE.Scene();
  private readonly overlayScene = new THREE.Scene();
  private readonly overlayCamera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  private readonly proxies = new Map<THREE.Mesh, THREE.Mesh>();
  private readonly materials = new Map<THREE.Material, THREE.MeshBasicMaterial>();
  private readonly size = new THREE.Vector2();
  private readonly pixel = new THREE.Vector2(1, 1);
  private readonly overlay = new THREE.Mesh(
    new THREE.PlaneGeometry(2, 2),
    new THREE.ShaderMaterial({
      uniforms: {
        mask: { value: this.mask.texture },
        pixel: { value: this.pixel },
        color: { value: new THREE.Color(0xd6eadb) },
      },
      vertexShader: `varying vec2 vUv;
        void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`,
      fragmentShader: `uniform sampler2D mask;
        uniform vec2 pixel;
        uniform vec3 color;
        varying vec2 vUv;
        void main() {
          vec4 center = texture2D(mask, vUv);
          float edge = 0.0;
          for (int x = -1; x <= 1; x++) {
            for (int y = -1; y <= 1; y++) {
              vec4 neighbor = texture2D(mask, vUv + vec2(float(x), float(y)) * pixel);
              edge = max(edge, abs(center.a - neighbor.a));
              // Surface normals expose roof/wall corners without triangle wireframes.
              if (center.a > 0.5 && neighbor.a > 0.5)
                edge = max(edge, smoothstep(0.25, 0.45, distance(center.rgb, neighbor.rgb)));
            }
          }
          gl_FragColor = vec4(color, edge * 0.9);
          #include <colorspace_fragment>
        }`,
      depthTest: false,
      depthWrite: false,
      transparent: true,
      toneMapped: false,
    }),
  );

  constructor() {
    this.overlay.frustumCulled = false;
    this.overlayScene.add(this.overlay);
  }

  private material(source: THREE.Material): THREE.MeshBasicMaterial {
    let result = this.materials.get(source);
    if (!result) {
      result = new THREE.MeshBasicMaterial();
      result.onBeforeCompile = (shader) => {
        shader.vertexShader = `varying vec3 contourNormal;\n${shader.vertexShader}`.replace(
          "#include <begin_vertex>",
          "#include <begin_vertex>\ncontourNormal = normalize(normalMatrix * normal);",
        );
        shader.fragmentShader = `varying vec3 contourNormal;\n${shader.fragmentShader}`
          .replace(
            "#include <opaque_fragment>",
            "gl_FragColor = vec4(normalize(contourNormal) * 0.5 + 0.5, 1.0);",
          )
          .replace("#include <colorspace_fragment>", "");
        // Some atlases store provenance in alpha; only physical coverage cuts holes.
        if (
          source.userData.source_ownership_fill === "synthesized" &&
          source.userData.foliage_physical_opacity !== true
        ) {
          shader.fragmentShader = shader.fragmentShader.replace(
            "#include <map_fragment>",
            THREE.ShaderChunk.map_fragment.replace(
              "diffuseColor *= sampledDiffuseColor;",
              "sampledDiffuseColor.a = 1.0; diffuseColor *= sampledDiffuseColor;",
            ),
          );
        }
      };
      result.customProgramCacheKey = () =>
        `asset-contour-normal-v1:${source.userData.source_ownership_fill}:${source.userData.foliage_physical_opacity}`;
      this.materials.set(source, result);
    }
    const mapped = source as THREE.MeshBasicMaterial;
    const map = mapped.map ?? null;
    const alphaMap = mapped.alphaMap ?? null;
    const alphaTest = Math.max(source.alphaTest, 0.1);
    if (
      result.map !== map ||
      result.alphaMap !== alphaMap ||
      result.alphaTest !== alphaTest ||
      result.side !== source.side
    )
      result.needsUpdate = true;
    result.map = map;
    result.alphaMap = alphaMap;
    result.alphaTest = alphaTest;
    result.opacity = source.opacity;
    result.side = source.side;
    result.visible = source.visible;
    result.toneMapped = false;
    return result;
  }

  private sync(roots: readonly THREE.Object3D[]): void {
    const active = new Set<THREE.Mesh>();
    const activeMaterials = new Set<THREE.Material>();
    for (const root of roots) {
      root.updateWorldMatrix(true, true);
      let ancestorsVisible = true;
      for (let parent = root.parent; parent; parent = parent.parent)
        ancestorsVisible &&= parent.visible;
      if (ancestorsVisible)
        root.traverseVisible((node) => {
          if (!(node instanceof THREE.Mesh)) return;
          if (active.has(node)) return;
          active.add(node);
          let proxy = this.proxies.get(node);
          if (!proxy) {
            proxy = new THREE.Mesh(node.geometry);
            // The constructor's default material is owned only by this temporary proxy.
            (proxy.material as THREE.Material).dispose();
            proxy.matrixAutoUpdate = false;
            this.proxies.set(node, proxy);
            this.maskScene.add(proxy);
          }
          proxy.geometry = node.geometry;
          proxy.matrix.copy(node.matrixWorld);
          proxy.layers.mask = node.layers.mask;
          proxy.renderOrder = node.renderOrder;
          const material = (source: THREE.Material) => {
            activeMaterials.add(source);
            return this.material(source);
          };
          proxy.material = Array.isArray(node.material)
            ? node.material.map(material)
            : material(node.material);
        });
    }
    for (const [source, proxy] of this.proxies)
      if (!active.has(source)) {
        this.maskScene.remove(proxy);
        this.proxies.delete(source);
      }
    for (const [source, material] of this.materials)
      if (!activeMaterials.has(source)) {
        material.dispose();
        this.materials.delete(source);
      }
  }

  /** Render the ordinary scene with transparent asset interiors and overlaid contours. */
  render(
    renderer: THREE.WebGLRenderer,
    scene: THREE.Scene,
    camera: THREE.Camera,
    objectsRoot: THREE.Object3D | readonly THREE.Object3D[],
  ): void {
    const roots = objectsRoot instanceof THREE.Object3D ? [objectsRoot] : objectsRoot;
    this.sync(roots);
    const target = renderer.getRenderTarget();
    renderer.getDrawingBufferSize(this.size);
    const width = target?.width ?? this.size.x;
    const height = target?.height ?? this.size.y;
    this.mask.setSize(width, height);
    this.pixel.set(1 / width, 1 / height);
    const visibility = new Map(roots.map((root) => [root, root.visible]));
    const autoClear = renderer.autoClear;
    const clearColor = renderer.getClearColor(new THREE.Color());
    const clearAlpha = renderer.getClearAlpha();
    const viewport = renderer.getViewport(new THREE.Vector4());
    const scissor = renderer.getScissor(new THREE.Vector4());
    const scissorTest = renderer.getScissorTest();
    try {
      for (const root of roots) root.visible = false;
      renderer.render(scene, camera);
      for (const [root, visible] of visibility) root.visible = visible;
      renderer.setRenderTarget(this.mask);
      renderer.setScissorTest(false);
      renderer.setClearColor(0, 0);
      renderer.autoClear = true;
      renderer.render(this.maskScene, camera);
      renderer.setRenderTarget(target);
      renderer.setViewport(viewport);
      renderer.setScissor(scissor);
      renderer.setScissorTest(scissorTest);
      renderer.autoClear = false;
      renderer.render(this.overlayScene, this.overlayCamera);
    } finally {
      for (const [root, visible] of visibility) root.visible = visible;
      renderer.setRenderTarget(target);
      renderer.setViewport(viewport);
      renderer.setScissor(scissor);
      renderer.setScissorTest(scissorTest);
      renderer.setClearColor(clearColor, clearAlpha);
      renderer.autoClear = autoClear;
    }
  }

  dispose(): void {
    this.mask.dispose();
    this.overlay.geometry.dispose();
    this.overlay.material.dispose();
    for (const material of this.materials.values()) material.dispose();
    this.materials.clear();
    this.proxies.clear();
    this.maskScene.clear();
  }
}
