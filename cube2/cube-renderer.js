/**
 * CubeRenderer
 *
 * Uses Three.js when it is already present locally, and otherwise falls back
 * to a bundled DOM/canvas preview so `cube2/` can run without external CDNs.
 */

class ThreeCubeRenderer {
    constructor(container, width, height) {
        this.container = container;
        this.width = width;
        this.height = height;

        this.scene = new THREE.Scene();
        this.camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
        this.camera.position.set(3, 3, 3);
        this.camera.lookAt(0, 0, 0);
        this.defaultCameraPosition = new THREE.Vector3(3, 3, 3);
        this.defaultControlsTarget = new THREE.Vector3(0, 0, 0);

        this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        this.renderer.setSize(width, height);
        this.renderer.setPixelRatio(window.devicePixelRatio || 1);
        this.renderer.setClearColor(0x000000, 0);
        container.appendChild(this.renderer.domElement);

        const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
        this.scene.add(ambientLight);
        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
        directionalLight.position.set(5, 5, 5);
        this.scene.add(directionalLight);

        if (typeof THREE.OrbitControls !== 'undefined') {
            this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
            this.controls.enableDamping = true;
            this.controls.dampingFactor = 0.05;
            this.controls.enableZoom = false;
            this.controls.target.copy(this.defaultControlsTarget);
            this.controls.saveState();
        }

        this.cubeGroup = new THREE.Group();
        this.scene.add(this.cubeGroup);

        this.directionGuide = this._createDirectionGuide();
        this.directionGuide.visible = false;
        this.scene.add(this.directionGuide);

        this.isAnimating = false;
        this.animationQueue = [];
        this._animate();
    }

    setDirectionGuideVisible(visible) {
        if (this.directionGuide) {
            this.directionGuide.visible = visible;
        }
    }

    createCube(cubeState) {
        while (this.cubeGroup.children.length > 0) {
            const child = this.cubeGroup.children[0];
            this.cubeGroup.remove(child);
            if (child.geometry) {
                child.geometry.dispose();
            }
            if (child.material) {
                if (Array.isArray(child.material)) {
                    child.material.forEach((material) => material.dispose());
                } else {
                    child.material.dispose();
                }
            }
        }

        this.faceMeshes = [];

        const coreMesh = new THREE.Mesh(
            new THREE.BoxGeometry(1, 1, 1),
            new THREE.MeshStandardMaterial({
                color: 0x1e1e3a,
                roughness: 0.55,
                metalness: 0.06,
            })
        );
        this.cubeGroup.add(coreMesh);
        this.cubeMesh = coreMesh;

        const edgeLines = new THREE.LineSegments(
            new THREE.EdgesGeometry(new THREE.BoxGeometry(1.01, 1.01, 1.01)),
            new THREE.LineBasicMaterial({
                color: 0xffffff,
                transparent: true,
                opacity: 0.24,
            })
        );
        this.cubeGroup.add(edgeLines);

        const planeGeometry = new THREE.PlaneGeometry(0.98, 0.98);
        const faceConfigs = [
            { stateIdx: 0, position: [0, 0.501, 0], rotation: [-Math.PI / 2, 0, 0] },
            { stateIdx: 1, position: [0, -0.501, 0], rotation: [Math.PI / 2, 0, 0] },
            { stateIdx: 2, position: [0, 0, 0.501], rotation: [0, 0, 0] },
            { stateIdx: 3, position: [0, 0, -0.501], rotation: [0, Math.PI, 0] },
            { stateIdx: 4, position: [-0.501, 0, 0], rotation: [0, -Math.PI / 2, 0] },
            { stateIdx: 5, position: [0.501, 0, 0], rotation: [0, Math.PI / 2, 0] },
        ];

        faceConfigs.forEach((config) => {
            const mesh = new THREE.Mesh(
                planeGeometry.clone(),
                new THREE.MeshStandardMaterial({
                    map: this._createFaceTexture(cubeState.faces[config.stateIdx], '#2a2a4a'),
                    roughness: 0.28,
                    metalness: 0.08,
                })
            );
            mesh.position.set(...config.position);
            mesh.rotation.set(...config.rotation);
            this.cubeGroup.add(mesh);
            this.faceMeshes.push({ mesh, stateIdx: config.stateIdx });
        });
    }

    updateTextures(cubeState) {
        if (!this.faceMeshes?.length) {
            return;
        }

        this.faceMeshes.forEach((entry) => {
            const face = cubeState.faces[entry.stateIdx];
            const nextTexture = this._createFaceTexture(face, '#2a2a4a');
            if (entry.mesh.material.map) {
                entry.mesh.material.map.dispose();
            }
            entry.mesh.material.map = nextTexture;
            entry.mesh.material.needsUpdate = true;
        });
    }

    animateRoll(direction, duration = 600) {
        return new Promise((resolve) => {
            if (this.isAnimating) {
                this.animationQueue.push(() => this.animateRoll(direction, duration).then(resolve));
                return;
            }
            this.isAnimating = true;

            let axis;
            let angle;
            switch (direction) {
                case 'N':
                    axis = new THREE.Vector3(1, 0, 0);
                    angle = -Math.PI / 2;
                    break;
                case 'S':
                    axis = new THREE.Vector3(1, 0, 0);
                    angle = Math.PI / 2;
                    break;
                case 'E':
                    axis = new THREE.Vector3(0, 0, -1);
                    angle = -Math.PI / 2;
                    break;
                case 'W':
                    axis = new THREE.Vector3(0, 0, 1);
                    angle = -Math.PI / 2;
                    break;
                default:
                    this.isAnimating = false;
                    resolve();
                    return;
            }

            const pivot = new THREE.Group();
            this.scene.add(pivot);
            pivot.position.copy(this.cubeGroup.position);

            switch (direction) {
                case 'N':
                    pivot.position.z -= 0.5;
                    pivot.position.y -= 0.5;
                    break;
                case 'S':
                    pivot.position.z += 0.5;
                    pivot.position.y -= 0.5;
                    break;
                case 'E':
                    pivot.position.x += 0.5;
                    pivot.position.y -= 0.5;
                    break;
                case 'W':
                    pivot.position.x -= 0.5;
                    pivot.position.y -= 0.5;
                    break;
            }

            this.scene.remove(this.cubeGroup);
            pivot.add(this.cubeGroup);
            this.cubeGroup.position.sub(pivot.position);

            const startQuat = new THREE.Quaternion();
            const endQuat = new THREE.Quaternion().setFromAxisAngle(axis, angle);
            const startTime = performance.now();

            const animateFrame = () => {
                const elapsed = performance.now() - startTime;
                const progress = Math.min(elapsed / duration, 1);
                const eased = progress < 0.5
                    ? 2 * progress * progress
                    : 1 - Math.pow(-2 * progress + 2, 2) / 2;

                const currentQuat = new THREE.Quaternion().slerpQuaternions(startQuat, endQuat, eased);
                pivot.quaternion.copy(currentQuat);

                if (progress < 1) {
                    requestAnimationFrame(animateFrame);
                    return;
                }

                pivot.quaternion.copy(endQuat);
                const worldPos = new THREE.Vector3();
                const worldQuat = new THREE.Quaternion();
                this.cubeGroup.getWorldPosition(worldPos);
                this.cubeGroup.getWorldQuaternion(worldQuat);

                pivot.remove(this.cubeGroup);
                this.scene.add(this.cubeGroup);

                worldPos.x = Math.round(worldPos.x);
                worldPos.y = Math.round(worldPos.y);
                worldPos.z = Math.round(worldPos.z);
                this.cubeGroup.position.copy(worldPos);
                this.cubeGroup.quaternion.copy(worldQuat);
                this.scene.remove(pivot);

                this.isAnimating = false;
                resolve();

                if (this.animationQueue.length > 0) {
                    const next = this.animationQueue.shift();
                    next();
                }
            };

            requestAnimationFrame(animateFrame);
        });
    }

    resetTransform() {
        this.cubeGroup.position.set(0, 0, 0);
        this.cubeGroup.quaternion.identity();
    }

    resetView() {
        this.resetTransform();
        this.camera.position.copy(this.defaultCameraPosition);
        this.camera.lookAt(this.defaultControlsTarget);

        if (this.controls) {
            if (typeof this.controls.reset === 'function') {
                this.controls.reset();
            }
            this.controls.target.copy(this.defaultControlsTarget);
            this.controls.update();
        }
    }

    resize(width, height) {
        this.width = width;
        this.height = height;
        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height);
    }

    _createFaceTexture(face, bgColor) {
        const texSize = 256;
        const texCanvas = generateFaceTexture(face, texSize, bgColor);
        const ctx = texCanvas.getContext('2d');
        ctx.strokeStyle = 'rgba(255,255,255,0.3)';
        ctx.lineWidth = 4;
        ctx.strokeRect(2, 2, texSize - 4, texSize - 4);

        const texture = new THREE.CanvasTexture(texCanvas);
        texture.magFilter = THREE.LinearFilter;
        texture.minFilter = THREE.LinearMipmapLinearFilter;
        return texture;
    }

    _createDirectionGuide() {
        const group = new THREE.Group();
        group.position.set(0, -1.08, 0);

        const ring = new THREE.Mesh(
            new THREE.RingGeometry(1.12, 1.24, 64),
            new THREE.MeshBasicMaterial({
                color: 0x64c8ff,
                transparent: true,
                opacity: 0.16,
                side: THREE.DoubleSide,
            })
        );
        ring.rotation.x = -Math.PI / 2;
        group.add(ring);

        const center = new THREE.Mesh(
            new THREE.CircleGeometry(0.09, 28),
            new THREE.MeshBasicMaterial({
                color: 0x64c8ff,
                transparent: true,
                opacity: 0.35,
                side: THREE.DoubleSide,
            })
        );
        center.rotation.x = -Math.PI / 2;
        group.add(center);

        const directions = [
            { label: 'Up', dir: new THREE.Vector3(0, 0, -1), color: 0x7dd3fc },
            { label: 'Down', dir: new THREE.Vector3(0, 0, 1), color: 0x7dd3fc },
            { label: 'Left', dir: new THREE.Vector3(-1, 0, 0), color: 0xa78bfa },
            { label: 'Right', dir: new THREE.Vector3(1, 0, 0), color: 0xa78bfa },
        ];

        directions.forEach((item) => {
            const arrow = new THREE.ArrowHelper(
                item.dir,
                new THREE.Vector3(0, 0, 0),
                1.42,
                item.color,
                0.4,
                0.22
            );
            group.add(arrow);

            const label = this._createTextSprite(item.label, item.color);
            label.position.copy(item.dir.clone().multiplyScalar(1.72));
            label.position.y = 0.16;
            label.scale.set(1.16, 0.38, 1);
            group.add(label);
        });

        return group;
    }

    _createTextSprite(text, color) {
        const canvas = document.createElement('canvas');
        canvas.width = 384;
        canvas.height = 128;
        const ctx = canvas.getContext('2d');

        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = 'rgba(10, 10, 26, 0.82)';
        this._roundRect(ctx, 12, 14, canvas.width - 24, canvas.height - 28, 26);
        ctx.fill();

        ctx.strokeStyle = 'rgba(255,255,255,0.12)';
        ctx.lineWidth = 3;
        this._roundRect(ctx, 12, 14, canvas.width - 24, canvas.height - 28, 26);
        ctx.stroke();

        ctx.fillStyle = `#${color.toString(16).padStart(6, '0')}`;
        ctx.font = 'bold 46px "Microsoft YaHei", Arial, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(text, canvas.width / 2, canvas.height / 2 + 3);

        const texture = new THREE.CanvasTexture(canvas);
        texture.needsUpdate = true;

        return new THREE.Sprite(new THREE.SpriteMaterial({
            map: texture,
            transparent: true,
            depthTest: true,
            depthWrite: false,
        }));
    }

    _roundRect(ctx, x, y, width, height, radius) {
        ctx.beginPath();
        ctx.moveTo(x + radius, y);
        ctx.lineTo(x + width - radius, y);
        ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
        ctx.lineTo(x + width, y + height - radius);
        ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
        ctx.lineTo(x + radius, y + height);
        ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
        ctx.lineTo(x, y + radius);
        ctx.quadraticCurveTo(x, y, x + radius, y);
        ctx.closePath();
    }

    _animate() {
        requestAnimationFrame(() => this._animate());
        if (this.controls) {
            this.controls.update();
        }
        this.renderer.render(this.scene, this.camera);
    }
}

class FlatCubeRenderer {
    constructor(container, width, height) {
        this.container = container;
        this.width = width;
        this.height = height;
        this.lastState = null;
        this.cubeMesh = null;
        this._buildLayout();
    }

    setDirectionGuideVisible(visible) {
        if (this.guide) {
            this.guide.classList.toggle('hidden', !visible);
        }
    }

    createCube(cubeState) {
        this.cubeMesh = { mode: 'flat-preview' };
        this.lastState = cubeState;
        this._renderState(cubeState);
    }

    updateTextures(cubeState) {
        if (!this.cubeMesh) {
            this.createCube(cubeState);
            return;
        }
        this.lastState = cubeState;
        this._renderState(cubeState);
    }

    animateRoll() {
        return Promise.resolve();
    }

    resetView() {
        if (this.lastState) {
            this._renderState(this.lastState);
        }
    }

    resize(width, height) {
        this.width = width;
        this.height = height;
    }

    _buildLayout() {
        this.container.innerHTML = '';
        const root = document.createElement('div');
        root.className = 'cube-fallback cube-local-preview';

        const note = document.createElement('div');
        note.className = 'cube-local-preview-note';
        note.textContent = 'Local Preview Mode';

        const stage = document.createElement('div');
        stage.className = 'cube-local-preview-stage';

        this.topFace = this._createFaceCard('Top');
        this.frontFace = this._createFaceCard('Front');
        this.rightFace = this._createFaceCard('Right');

        stage.appendChild(this.topFace.card);
        stage.appendChild(this.frontFace.card);
        stage.appendChild(this.rightFace.card);

        const guide = document.createElement('div');
        guide.className = 'cube-local-preview-guide';
        ['^ Up', 'v Down', '< Left', '> Right'].forEach((label) => {
            const chip = document.createElement('span');
            chip.textContent = label;
            guide.appendChild(chip);
        });

        root.appendChild(note);
        root.appendChild(stage);
        root.appendChild(guide);
        this.container.appendChild(root);

        this.root = root;
        this.guide = guide;
    }

    _createFaceCard(label) {
        const card = document.createElement('div');
        card.className = 'local-face-card';

        const title = document.createElement('div');
        title.className = 'local-face-label';
        title.textContent = label;

        const canvas = document.createElement('canvas');
        canvas.width = 128;
        canvas.height = 128;

        const meta = document.createElement('div');
        meta.className = 'local-face-meta';

        card.appendChild(title);
        card.appendChild(canvas);
        card.appendChild(meta);

        return { card, canvas, meta };
    }

    _renderState(cubeState) {
        const faces = Array.isArray(cubeState?.faces) ? cubeState.faces : [];
        this._paintFace(this.topFace, faces[0], 'Top');
        this._paintFace(this.frontFace, faces[2], 'Front');
        this._paintFace(this.rightFace, faces[5], 'Right');
    }

    _paintFace(target, face, fallbackLabel) {
        const normalizedFace = face || { patternId: '?', rotation: 0 };
        const ctx = target.canvas.getContext('2d');
        const textureCanvas = generateFaceTexture(normalizedFace, target.canvas.width, '#241f49');
        ctx.clearRect(0, 0, target.canvas.width, target.canvas.height);
        ctx.drawImage(textureCanvas, 0, 0);
        target.meta.textContent = `${fallbackLabel}: ${normalizedFace.patternId} - ${Number(normalizedFace.rotation || 0)}`;
    }
}

class CubeRenderer {
    constructor(container, width, height) {
        this.impl = (window.THREE && typeof window.THREE.WebGLRenderer === 'function')
            ? new ThreeCubeRenderer(container, width, height)
            : new FlatCubeRenderer(container, width, height);
    }

    get cubeMesh() {
        return this.impl.cubeMesh;
    }

    setDirectionGuideVisible(visible) {
        this.impl.setDirectionGuideVisible(visible);
    }

    createCube(cubeState) {
        this.impl.createCube(cubeState);
    }

    updateTextures(cubeState) {
        this.impl.updateTextures(cubeState);
    }

    animateRoll(direction, duration = 600) {
        return this.impl.animateRoll(direction, duration);
    }

    resetView() {
        this.impl.resetView();
    }

    resize(width, height) {
        this.impl.resize(width, height);
    }
}
