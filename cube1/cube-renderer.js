/**
 * CubeRenderer - 3D rendering of the cube using Three.js
 */

class CubeRenderer {
    /**
     * @param {HTMLElement} container - DOM element to render into
     * @param {number} width - canvas width
     * @param {number} height - canvas height
     */
    constructor(container, width, height) {
        this.container = container;
        this.width = width;
        this.height = height;

        // Three.js setup
        this.scene = new THREE.Scene();
        this.camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
        this.camera.position.set(3, 3, 3);
        this.camera.lookAt(0, 0, 0);
        this.defaultCameraPosition = new THREE.Vector3(3, 3, 3);
        this.defaultControlsTarget = new THREE.Vector3(0, 0, 0);

        this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        this.renderer.setSize(width, height);
        this.renderer.setPixelRatio(window.devicePixelRatio);
        this.renderer.setClearColor(0x000000, 0);
        container.appendChild(this.renderer.domElement);

        // Lighting
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
        this.scene.add(ambientLight);
        const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
        dirLight.position.set(5, 5, 5);
        this.scene.add(dirLight);

        // Orbit controls (optional, for user interaction)
        if (typeof THREE.OrbitControls !== 'undefined') {
            this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
            this.controls.enableDamping = true;
            this.controls.dampingFactor = 0.05;
            this.controls.enableZoom = false;
            this.controls.target.copy(this.defaultControlsTarget);
            this.controls.saveState();
        }

        // Cube group
        this.cubeGroup = new THREE.Group();
        this.scene.add(this.cubeGroup);

        // Direction guide used in reverse mode
        this.directionGuide = this._createDirectionGuide();
        this.directionGuide.visible = false;
        this.scene.add(this.directionGuide);

        // Animation state
        this.isAnimating = false;
        this.animationQueue = [];

        // Start render loop
        this._animate();
    }

    /**
     * Create the cube mesh with face textures.
     * @param {CubeState} cubeState
     */
    createCube(cubeState) {
        // Remove old cube
        while (this.cubeGroup.children.length > 0) {
            const child = this.cubeGroup.children[0];
            this.cubeGroup.remove(child);
            if (child.geometry) child.geometry.dispose();
            if (child.material) {
                if (Array.isArray(child.material)) {
                    child.material.forEach(m => m.dispose());
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
                metalness: 0.06
            })
        );
        this.cubeGroup.add(coreMesh);
        this.cubeMesh = coreMesh;

        const edgeLines = new THREE.LineSegments(
            new THREE.EdgesGeometry(new THREE.BoxGeometry(1.01, 1.01, 1.01)),
            new THREE.LineBasicMaterial({
                color: 0xffffff,
                transparent: true,
                opacity: 0.24
            })
        );
        this.cubeGroup.add(edgeLines);

        const planeGeometry = new THREE.PlaneGeometry(0.98, 0.98);
        const faceConfigs = [
            { stateIdx: 0, position: [0, 0.501, 0], rotation: [-Math.PI / 2, 0, 0] }, // top
            { stateIdx: 1, position: [0, -0.501, 0], rotation: [Math.PI / 2, 0, 0] }, // bottom
            { stateIdx: 2, position: [0, 0, 0.501], rotation: [0, 0, 0] }, // front
            { stateIdx: 3, position: [0, 0, -0.501], rotation: [0, Math.PI, 0] }, // back
            { stateIdx: 4, position: [-0.501, 0, 0], rotation: [0, -Math.PI / 2, 0] }, // left
            { stateIdx: 5, position: [0.501, 0, 0], rotation: [0, Math.PI / 2, 0] } // right
        ];

        faceConfigs.forEach((config) => {
            const mesh = new THREE.Mesh(
                planeGeometry.clone(),
                new THREE.MeshStandardMaterial({
                    map: this._createFaceTexture(cubeState.faces[config.stateIdx], '#2a2a4a'),
                    roughness: 0.28,
                    metalness: 0.08
                })
            );
            mesh.position.set(...config.position);
            mesh.rotation.set(...config.rotation);
            this.cubeGroup.add(mesh);
            this.faceMeshes.push({
                mesh,
                stateIdx: config.stateIdx
            });
        });
    }

    /**
     * Show or hide the 3D roll-direction guide.
     * The guide sits below the cube so it does not cover any face.
     */
    setDirectionGuideVisible(visible) {
        if (this.directionGuide) {
            this.directionGuide.visible = visible;
        }
    }

    /**
     * Update face textures to reflect new cube state.
     */
    updateTextures(cubeState) {
        if (!this.faceMeshes?.length) return;

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

    /**
     * Animate a roll in the given direction.
     * @param {string} direction - 'N','S','E','W'
     * @param {number} duration - animation duration in ms
     * @returns {Promise} resolves when animation completes
     */
    animateRoll(direction, duration = 600) {
        return new Promise((resolve) => {
            if (this.isAnimating) {
                this.animationQueue.push(() => this.animateRoll(direction, duration).then(resolve));
                return;
            }
            this.isAnimating = true;

            // Determine rotation axis and angle
            let axis, angle;
            switch (direction) {
                case 'N': axis = new THREE.Vector3(1, 0, 0); angle = -Math.PI / 2; break;
                case 'S': axis = new THREE.Vector3(1, 0, 0); angle = Math.PI / 2; break;
                case 'E': axis = new THREE.Vector3(0, 0, -1); angle = -Math.PI / 2; break;
                case 'W': axis = new THREE.Vector3(0, 0, 1); angle = -Math.PI / 2; break;
            }

            // Pivot point (edge the cube rolls over)
            const pivot = new THREE.Group();
            this.scene.add(pivot);
            pivot.position.copy(this.cubeGroup.position);

            // Set pivot offset based on direction
            switch (direction) {
                case 'N': pivot.position.z -= 0.5; pivot.position.y -= 0.5; break;
                case 'S': pivot.position.z += 0.5; pivot.position.y -= 0.5; break;
                case 'E': pivot.position.x += 0.5; pivot.position.y -= 0.5; break;
                case 'W': pivot.position.x -= 0.5; pivot.position.y -= 0.5; break;
            }

            // Move cubeGroup to be child of pivot
            this.scene.remove(this.cubeGroup);
            pivot.add(this.cubeGroup);
            this.cubeGroup.position.sub(pivot.position);

            const startQuat = new THREE.Quaternion();
            const endQuat = new THREE.Quaternion().setFromAxisAngle(axis, angle);
            const startTime = performance.now();

            const animateFrame = () => {
                const elapsed = performance.now() - startTime;
                const t = Math.min(elapsed / duration, 1);

                // Ease in-out
                const eased = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;

                const currentQuat = new THREE.Quaternion().slerpQuaternions(startQuat, endQuat, eased);
                pivot.quaternion.copy(currentQuat);

                if (t < 1) {
                    requestAnimationFrame(animateFrame);
                } else {
                    // Finalize: move cubeGroup back to scene
                    pivot.quaternion.copy(endQuat);
                    const worldPos = new THREE.Vector3();
                    const worldQuat = new THREE.Quaternion();
                    this.cubeGroup.getWorldPosition(worldPos);
                    this.cubeGroup.getWorldQuaternion(worldQuat);

                    pivot.remove(this.cubeGroup);
                    this.scene.add(this.cubeGroup);

                    // Snap position to grid
                    worldPos.x = Math.round(worldPos.x);
                    worldPos.y = Math.round(worldPos.y);
                    worldPos.z = Math.round(worldPos.z);
                    this.cubeGroup.position.copy(worldPos);
                    this.cubeGroup.quaternion.copy(worldQuat);

                    // Clean up pivot
                    this.scene.remove(pivot);

                    this.isAnimating = false;
                    resolve();

                    // Process queue
                    if (this.animationQueue.length > 0) {
                        const next = this.animationQueue.shift();
                        next();
                    }
                }
            };
            requestAnimationFrame(animateFrame);
        });
    }

    /**
     * Reset cube to origin position without accumulated rotations.
     * Used after updating textures to avoid rotation drift.
     */
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

    _createDirectionGuide() {
        const group = new THREE.Group();
        group.position.set(0, -1.08, 0);

        const ring = new THREE.Mesh(
            new THREE.RingGeometry(1.12, 1.24, 64),
            new THREE.MeshBasicMaterial({
                color: 0x64c8ff,
                transparent: true,
                opacity: 0.16,
                side: THREE.DoubleSide
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
                side: THREE.DoubleSide
            })
        );
        center.rotation.x = -Math.PI / 2;
        group.add(center);

        const directions = [
            { label: '↑ 上滚', dir: new THREE.Vector3(0, 0, -1), color: 0x7dd3fc },
            { label: '↓ 下滚', dir: new THREE.Vector3(0, 0, 1), color: 0x7dd3fc },
            { label: '← 左滚', dir: new THREE.Vector3(-1, 0, 0), color: 0xa78bfa },
            { label: '→ 右滚', dir: new THREE.Vector3(1, 0, 0), color: 0xa78bfa }
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
            depthWrite: false
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
        if (this.controls) this.controls.update();
        this.renderer.render(this.scene, this.camera);
    }

    resize(width, height) {
        this.width = width;
        this.height = height;
        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height);
    }
}
