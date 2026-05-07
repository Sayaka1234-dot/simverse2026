/**
 * CubeEngine - tracks the state of a cube as it rolls on a grid.
 *
 * Face indices:
 *   0 = Top, 1 = Bottom, 2 = Front, 3 = Back, 4 = Left, 5 = Right
 *
 * Net order:
 *   [top, front, right, back, left, bottom]
 */

const FACE_KEYS = ['TOP', 'BOTTOM', 'FRONT', 'BACK', 'LEFT', 'RIGHT'];
const NET_FACE_ORDER = ['TOP', 'FRONT', 'RIGHT', 'BACK', 'LEFT', 'BOTTOM'];
const VALID_ROTATIONS = [0, 90, 180, 270];
const NET_TO_CUBE_ROTATION_OFFSETS = {
    TOP: 0,
    BOTTOM: 0,
    FRONT: 0,
    BACK: 180,
    LEFT: 270,
    RIGHT: 90
};
const CUBE_TO_NET_ROTATION_OFFSETS = {
    TOP: 0,
    BOTTOM: 0,
    FRONT: 0,
    BACK: -180,
    LEFT: -270,
    RIGHT: -90
};

function normalizeRotation(rotation) {
    const numeric = Number(rotation ?? 0);
    if (!Number.isFinite(numeric)) {
        throw new Error(`Invalid rotation: ${rotation}`);
    }

    const normalized = ((numeric % 360) + 360) % 360;
    if (!VALID_ROTATIONS.includes(normalized)) {
        throw new Error(`Rotation must be one of 0/90/180/270, got: ${rotation}`);
    }

    return normalized;
}

function cloneFace(face) {
    if (!face || typeof face.patternId !== 'string' || !face.patternId.trim()) {
        throw new Error(`Invalid face payload: ${JSON.stringify(face)}`);
    }

    return {
        patternId: face.patternId,
        rotation: normalizeRotation(face.rotation),
        flipHorizontal: Boolean(face.flipHorizontal),
        flipVertical: Boolean(face.flipVertical)
    };
}

function normalizeMaybeUnknownFace(face) {
    if (!face || typeof face.patternId !== 'string' || !face.patternId.trim()) {
        throw new Error(`Invalid face payload: ${JSON.stringify(face)}`);
    }

    if (face.patternId === '?') {
        return {
            patternId: '?',
            rotation: 0,
            flipHorizontal: false,
            flipVertical: false
        };
    }

    return cloneFace(face);
}

function normalizeNetFace(faceOrPattern) {
    if (typeof faceOrPattern === 'string') {
        return {
            patternId: faceOrPattern,
            rotation: 0,
            flipHorizontal: false,
            flipVertical: false
        };
    }

    return cloneFace(faceOrPattern);
}

function normalizeNetFaces(netFaces) {
    if (!Array.isArray(netFaces) || netFaces.length !== 6) {
        throw new Error('Net must contain 6 faces in [top, front, right, back, left, bottom] order');
    }

    return netFaces.map((face) => normalizeNetFace(face));
}

function cloneSolutionFaceMap(solutionFaces) {
    if (!solutionFaces || typeof solutionFaces !== 'object') {
        throw new Error(`Invalid solution face map: ${JSON.stringify(solutionFaces)}`);
    }

    const result = {};
    FACE_KEYS.forEach((key) => {
        result[key] = cloneFace(solutionFaces[key]);
    });
    return result;
}

class CubeState {
    constructor(faces) {
        this.faces = faces.map((face) => cloneFace(face));
        this.x = 0;
        this.y = 0;
    }

    clone() {
        const next = new CubeState(this.faces);
        next.x = this.x;
        next.y = this.y;
        return next;
    }

    get top() { return this.faces[0]; }
    get bottom() { return this.faces[1]; }
    get front() { return this.faces[2]; }
    get back() { return this.faces[3]; }
    get left() { return this.faces[4]; }
    get right() { return this.faces[5]; }

    _remap(mapping, rotationAdjustments) {
        const old = this.faces.map((face) => ({ ...face }));

        for (let index = 0; index < 6; index += 1) {
            const previous = old[mapping[index]];
            this.faces[index] = {
                patternId: previous.patternId,
                rotation: normalizeRotation(previous.rotation + rotationAdjustments[index]),
                flipHorizontal: Boolean(previous.flipHorizontal),
                flipVertical: Boolean(previous.flipVertical)
            };
        }
    }

    rollNorth() {
        this._remap(
            [2, 3, 1, 0, 4, 5],
            [0, 180, 0, 180, -90, 90]
        );
        this.y -= 1;
        return this;
    }

    rollSouth() {
        this._remap(
            [3, 2, 0, 1, 4, 5],
            [180, 0, 0, 180, 90, -90]
        );
        this.y += 1;
        return this;
    }

    rollEast() {
        this._remap(
            [4, 5, 2, 3, 1, 0],
            [90, 90, 90, -90, 90, 90]
        );
        this.x += 1;
        return this;
    }

    rollWest() {
        this._remap(
            [5, 4, 2, 3, 0, 1],
            [-90, -90, -90, 90, -90, -90]
        );
        this.x -= 1;
        return this;
    }

    roll(direction) {
        switch (direction) {
            case 'N': return this.rollNorth();
            case 'S': return this.rollSouth();
            case 'E': return this.rollEast();
            case 'W': return this.rollWest();
            default:
                throw new Error(`Unknown direction: ${direction}`);
        }
    }
}

function cubeFromNet(netInput) {
    const netFaces = normalizeNetFaces(netInput);

    return new CubeState([
        {
            patternId: netFaces[0].patternId,
            rotation: netFaces[0].rotation,
            flipHorizontal: netFaces[0].flipHorizontal,
            flipVertical: netFaces[0].flipVertical
        },
        {
            patternId: netFaces[5].patternId,
            rotation: netFaces[5].rotation,
            flipHorizontal: netFaces[5].flipHorizontal,
            flipVertical: netFaces[5].flipVertical
        },
        {
            patternId: netFaces[1].patternId,
            rotation: netFaces[1].rotation,
            flipHorizontal: netFaces[1].flipHorizontal,
            flipVertical: netFaces[1].flipVertical
        },
        {
            patternId: netFaces[3].patternId,
            rotation: normalizeRotation(netFaces[3].rotation + 180),
            flipHorizontal: netFaces[3].flipHorizontal,
            flipVertical: netFaces[3].flipVertical
        },
        {
            patternId: netFaces[4].patternId,
            rotation: normalizeRotation(netFaces[4].rotation + 270),
            flipHorizontal: netFaces[4].flipHorizontal,
            flipVertical: netFaces[4].flipVertical
        },
        {
            patternId: netFaces[2].patternId,
            rotation: normalizeRotation(netFaces[2].rotation + 90),
            flipHorizontal: netFaces[2].flipHorizontal,
            flipVertical: netFaces[2].flipVertical
        }
    ]);
}

function cubeFromSolutionFaces(solutionFaces) {
    const normalized = cloneSolutionFaceMap(solutionFaces);

    return new CubeState([
        normalized.TOP,
        normalized.BOTTOM,
        normalized.FRONT,
        normalized.BACK,
        normalized.LEFT,
        normalized.RIGHT
    ]);
}

function buildNetFacesFromSolutionFaces(solutionFaces) {
    const normalized = cloneSolutionFaceMap(solutionFaces);

    return [
        cubeFaceToNetFace('TOP', normalized.TOP),
        cubeFaceToNetFace('FRONT', normalized.FRONT),
        cubeFaceToNetFace('RIGHT', normalized.RIGHT),
        cubeFaceToNetFace('BACK', normalized.BACK),
        cubeFaceToNetFace('LEFT', normalized.LEFT),
        cubeFaceToNetFace('BOTTOM', normalized.BOTTOM)
    ];
}

function cubeFaceToNetFace(slotKey, face) {
    const normalized = normalizeMaybeUnknownFace(face);
    if (normalized.patternId === '?') {
        return normalized;
    }

    return {
        patternId: normalized.patternId,
        rotation: normalizeRotation(normalized.rotation + (CUBE_TO_NET_ROTATION_OFFSETS[slotKey] ?? 0)),
        flipHorizontal: normalized.flipHorizontal,
        flipVertical: normalized.flipVertical
    };
}

function netFaceToCubeFace(slotKey, face) {
    const normalized = normalizeMaybeUnknownFace(face);
    if (normalized.patternId === '?') {
        return normalized;
    }

    return {
        patternId: normalized.patternId,
        rotation: normalizeRotation(normalized.rotation + (NET_TO_CUBE_ROTATION_OFFSETS[slotKey] ?? 0)),
        flipHorizontal: normalized.flipHorizontal,
        flipVertical: normalized.flipVertical
    };
}

function buildSolutionFacesFromCube(cube) {
    return {
        TOP: cloneFace(cube.top),
        BOTTOM: cloneFace(cube.bottom),
        FRONT: cloneFace(cube.front),
        BACK: cloneFace(cube.back),
        LEFT: cloneFace(cube.left),
        RIGHT: cloneFace(cube.right)
    };
}

function simulatePath(initialState, directions) {
    const cube = initialState.clone();
    const results = [{
        patternId: cube.bottom.patternId,
        rotation: cube.bottom.rotation,
        flipHorizontal: Boolean(cube.bottom.flipHorizontal),
        flipVertical: Boolean(cube.bottom.flipVertical),
        x: cube.x,
        y: cube.y
    }];

    for (const direction of directions) {
        cube.roll(direction);
        results.push({
            patternId: cube.bottom.patternId,
            rotation: cube.bottom.rotation,
            flipHorizontal: Boolean(cube.bottom.flipHorizontal),
            flipVertical: Boolean(cube.bottom.flipVertical),
            x: cube.x,
            y: cube.y
        });
    }

    return results;
}

function bottomFaceToPathViewFace(face) {
    return {
        patternId: face.patternId,
        rotation: normalizeRotation(face.rotation ?? 0),
        flipHorizontal: Boolean(face.flipHorizontal),
        flipVertical: Boolean(face.flipVertical),
        x: face.x,
        y: face.y
    };
}

function simulatePathViewFaces(initialState, directions) {
    return simulatePath(initialState, directions).map(bottomFaceToPathViewFace);
}

function flipFaceHorizontally(face) {
    const normalized = normalizeMaybeUnknownFace(face);
    return {
        ...normalized,
        flipHorizontal: !normalized.flipHorizontal
    };
}

function flipFaceVertically(face) {
    const normalized = normalizeMaybeUnknownFace(face);
    return {
        ...normalized,
        flipVertical: !normalized.flipVertical
    };
}

function flipFaceSequenceVertically(faces) {
    if (!Array.isArray(faces)) {
        return [];
    }

    return faces.map((face) => flipFaceVertically(face));
}

function bottomFaceToStampFace(face) {
    return bottomFaceToPathViewFace(face);
}

function simulateStampPath(initialState, directions) {
    return simulatePathViewFaces(initialState, directions);
}

function simulatePathStates(initialState, directions) {
    const cube = initialState.clone();
    const states = [cube.clone()];

    for (const direction of directions) {
        cube.roll(direction);
        states.push(cube.clone());
    }

    return states;
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        FACE_KEYS,
        NET_FACE_ORDER,
        CubeState,
        normalizeRotation,
        cloneFace,
        normalizeMaybeUnknownFace,
        normalizeNetFaces,
        NET_TO_CUBE_ROTATION_OFFSETS,
        CUBE_TO_NET_ROTATION_OFFSETS,
        cubeFromNet,
        cubeFromSolutionFaces,
        buildNetFacesFromSolutionFaces,
        buildSolutionFacesFromCube,
        cubeFaceToNetFace,
        netFaceToCubeFace,
        simulatePath,
        simulatePathViewFaces,
        flipFaceHorizontally,
        flipFaceVertically,
        flipFaceSequenceVertically,
        simulateStampPath,
        simulatePathStates,
        bottomFaceToPathViewFace,
        bottomFaceToStampFace
    };
}
