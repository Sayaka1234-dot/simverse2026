const fs = require('fs');
const path = require('path');
const {
    FACE_KEYS,
    CubeState,
    normalizeRotation,
    cloneFace,
    normalizeNetFaces,
    cubeFromNet,
    cubeFromSolutionFaces,
    buildNetFacesFromSolutionFaces,
    buildSolutionFacesFromCube,
    cubeFaceToNetFace,
    simulatePath,
    simulatePathViewFaces,
    flipFaceSequenceVertically
} = require('./cube-engine');

const MODE_KEYS = ['reconstruct'];
const RECONSTRUCTION_SLOT_TO_NET_INDEX = {
    TOP: 0,
    FRONT: 1,
    RIGHT: 2,
    BACK: 3,
    LEFT: 4,
    BOTTOM: 5
};
const LEVELS_ROOT = path.join(__dirname, 'levels');
const CATALOG_JSON_PATH = path.join(LEVELS_ROOT, 'index.json');
const CATALOG_JS_PATH = path.join(LEVELS_ROOT, 'catalog.generated.js');
const PATH_DIRECTIONS = new Set(['N', 'S', 'E', 'W']);

function inferDifficultyFromMoves(moveCount) {
    if (moveCount <= 2) return 1;
    if (moveCount <= 4) return 2;
    if (moveCount <= 6) return 3;
    if (moveCount <= 8) return 4;
    return 5;
}

function stepPosition(position, direction) {
    switch (direction) {
        case 'N': return { x: position.x, y: position.y - 1 };
        case 'S': return { x: position.x, y: position.y + 1 };
        case 'E': return { x: position.x + 1, y: position.y };
        case 'W': return { x: position.x - 1, y: position.y };
        default:
            throw new Error(`Unknown direction: ${direction}`);
    }
}

function computeBoard(pathDirections) {
    let x = 0;
    let y = 0;
    let minX = 0;
    let maxX = 0;
    let minY = 0;
    let maxY = 0;

    for (const dir of pathDirections) {
        ({ x, y } = stepPosition({ x, y }, dir));
        minX = Math.min(minX, x);
        maxX = Math.max(maxX, x);
        minY = Math.min(minY, y);
        maxY = Math.max(maxY, y);
    }

    const padding = 1;
    return {
        startX: -minX + padding,
        startY: -minY + padding,
        gridWidth: maxX - minX + 1 + padding * 2,
        gridHeight: maxY - minY + 1 + padding * 2
    };
}

function normalizeFace(face, label = 'face') {
    try {
        return cloneFace(face);
    } catch (error) {
        throw new Error(`${label}: ${error.message}`);
    }
}

function normalizeBottomFace(face, label = 'bottom face') {
    const normalized = normalizeFace(face, label);
    return {
        patternId: normalized.patternId,
        rotation: normalized.rotation,
        flipHorizontal: normalized.flipHorizontal,
        flipVertical: normalized.flipVertical,
        x: Number.isFinite(Number(face?.x)) ? Number(face.x) : undefined,
        y: Number.isFinite(Number(face?.y)) ? Number(face.y) : undefined
    };
}

function normalizeFaceSequence(sequence, label, mapper = normalizeFace) {
    if (!Array.isArray(sequence)) {
        throw new Error(`${label} must be an array`);
    }

    return sequence.map((face, index) => mapper(face, `${label}[${index}]`));
}

function normalizeSolutionFaceMap(faceMap, label = 'answers.solutionFaces') {
    if (!faceMap || typeof faceMap !== 'object' || Array.isArray(faceMap)) {
        throw new Error(`${label} must be an object`);
    }

    const result = {};
    FACE_KEYS.forEach((key) => {
        result[key] = normalizeFace(faceMap[key], `${label}.${key}`);
    });
    return result;
}

function normalizePath(pathDirections, label = 'path') {
    if (!Array.isArray(pathDirections)) {
        throw new Error(`${label} must be an array`);
    }

    pathDirections.forEach((dir, index) => {
        if (!PATH_DIRECTIONS.has(dir)) {
            throw new Error(`${label}[${index}] has invalid direction "${dir}"`);
        }
    });

    return [...pathDirections];
}

function facesEqual(a, b) {
    return !!a &&
        !!b &&
        a.patternId === b.patternId &&
        normalizeRotation(a.rotation) === normalizeRotation(b.rotation) &&
        Boolean(a.flipHorizontal) === Boolean(b.flipHorizontal) &&
        Boolean(a.flipVertical) === Boolean(b.flipVertical);
}

function bottomFacesEqual(a, b) {
    return facesEqual(a, b) &&
        Number(a.x) === Number(b.x) &&
        Number(a.y) === Number(b.y);
}

function buildSlotTrackingCube() {
    return new CubeState([
        { patternId: 'TOP', rotation: 0 },
        { patternId: 'BOTTOM', rotation: 0 },
        { patternId: 'FRONT', rotation: 0 },
        { patternId: 'BACK', rotation: 0 },
        { patternId: 'LEFT', rotation: 0 },
        { patternId: 'RIGHT', rotation: 0 }
    ]);
}

function buildLevelCube(level) {
    const cube = cubeFromNet(level.netFaces);
    cube.x = level.startX;
    cube.y = level.startY;
    return cube;
}

function buildSolutionFaces(level) {
    return buildSolutionFacesFromCube(buildLevelCube(level));
}

function buildBottomFacesFromCube(cube, directions) {
    return simulatePath(cube, directions).map((face) => ({
        patternId: face.patternId,
        rotation: normalizeRotation(face.rotation),
        flipHorizontal: Boolean(face.flipHorizontal),
        flipVertical: Boolean(face.flipVertical),
        x: face.x,
        y: face.y
    }));
}

function buildBottomFaces(level) {
    return buildBottomFacesFromCube(buildLevelCube(level), level.path);
}

function buildReverseTargets(level) {
    return buildBottomFaces(level).slice(1).map((face) => face.patternId);
}

function buildReconstructionPromptFromCube(cube, directions) {
    const rawObservedPathFaces = simulatePathViewFaces(cube, directions).slice(1).map((face) => ({
        patternId: face.patternId,
        rotation: normalizeRotation(face.rotation),
        flipHorizontal: Boolean(face.flipHorizontal),
        flipVertical: Boolean(face.flipVertical)
    }));
    const observedPathFaces = flipFaceSequenceVertically(rawObservedPathFaces);

    const slotSequence = simulatePath(buildSlotTrackingCube(), directions)
        .slice(1)
        .map((face) => face.patternId);
    const requiredSlots = [...new Set(slotSequence)];

    return {
        directions: [...directions],
        observedPathFaces,
        slotSequence,
        requiredSlots,
        requiredCount: requiredSlots.length
    };
}

function buildReconstructionPrompt(level) {
    return buildReconstructionPromptFromCube(buildLevelCube(level), level.path);
}

function buildReconstructionTemplateFaces(netFaces, requiredSlots) {
    const requiredSet = new Set(requiredSlots);
    const template = {};

    Object.entries(RECONSTRUCTION_SLOT_TO_NET_INDEX).forEach(([slotKey, netIndex]) => {
        template[slotKey] = requiredSet.has(slotKey)
            ? cloneFace(netFaces[netIndex])
            : { patternId: '?', rotation: 0 };
    });

    return template;
}

function buildDefaultGroups(levels) {
    const buckets = new Map();

    levels.forEach((level) => {
        const key = String(level.difficulty);
        if (!buckets.has(key)) {
            buckets.set(key, {
                key,
                difficulty: level.difficulty,
                minMoves: level.moveCount,
                maxMoves: level.moveCount,
                count: 0
            });
        }

        const bucket = buckets.get(key);
        bucket.minMoves = Math.min(bucket.minMoves, level.moveCount);
        bucket.maxMoves = Math.max(bucket.maxMoves, level.moveCount);
        bucket.count += 1;
    });

    return [...buckets.values()]
        .sort((a, b) => a.difficulty - b.difficulty)
        .map((bucket) => ({
            key: `tier-${bucket.difficulty}`,
            label: `Difficulty ${bucket.difficulty}`,
            description: `${bucket.minMoves}-${bucket.maxMoves} moves`,
            minMoves: bucket.minMoves,
            maxMoves: bucket.maxMoves,
            count: bucket.count
        }));
}

function sortLevels(a, b) {
    const aId = Number(a.id);
    const bId = Number(b.id);

    if (Number.isFinite(aId) && Number.isFinite(bId) && aId !== bId) {
        return aId - bId;
    }

    return String(a.code || a.name || '').localeCompare(String(b.code || b.name || ''));
}

function ensureLevelRoot() {
    fs.mkdirSync(LEVELS_ROOT, { recursive: true });
    MODE_KEYS.forEach((mode) => {
        fs.mkdirSync(path.join(LEVELS_ROOT, mode), { recursive: true });
    });
}

function ensureBaseLevel(rawLevel, fallbackId, mode, sourcePath) {
    if (!rawLevel || typeof rawLevel !== 'object' || Array.isArray(rawLevel)) {
        throw new Error(`Level file must export one JSON object${sourcePath ? ` (${sourcePath})` : ''}`);
    }

    const pathDirections = normalizePath(rawLevel.path ?? rawLevel.prompt?.directions, 'path');
    const netFaces = rawLevel.netFaces
        ? normalizeNetFaces(rawLevel.netFaces)
        : (Array.isArray(rawLevel.netPatterns) && rawLevel.netPatterns.length === 6
            ? normalizeNetFaces(rawLevel.netPatterns)
            : null);

    if (!netFaces) {
        throw new Error(`Level must contain netFaces with 6 oriented faces${sourcePath ? ` (${sourcePath})` : ''}`);
    }

    const board = computeBoard(pathDirections);
    const moveCount = rawLevel.moveCount ?? pathDirections.length;
    const difficulty = rawLevel.difficulty ?? inferDifficultyFromMoves(moveCount);

    return {
        id: rawLevel.id ?? fallbackId,
        code: rawLevel.code ?? `${mode.toUpperCase()}-${String(fallbackId).padStart(3, '0')}`,
        mode,
        name: rawLevel.name ?? `${mode} level ${String(fallbackId).padStart(3, '0')}`,
        description: rawLevel.description ?? `${mode} puzzle with ${moveCount} moves`,
        netLayout: rawLevel.netLayout ?? 'standard_cross',
        netFaces,
        netPatterns: netFaces.map((face) => face.patternId),
        path: pathDirections,
        startX: rawLevel.startX ?? board.startX,
        startY: rawLevel.startY ?? board.startY,
        gridWidth: rawLevel.gridWidth ?? board.gridWidth,
        gridHeight: rawLevel.gridHeight ?? board.gridHeight,
        difficulty,
        moveCount,
        tier: rawLevel.tier ?? difficulty,
        tierLabel: rawLevel.tierLabel ?? `Difficulty ${difficulty}`,
        sourceFile: sourcePath ? path.relative(__dirname, sourcePath).replace(/\\/g, '/') : null
    };
}

function validateNetFacesAgainstSolution(level, solutionFaces) {
    const expectedNetFaces = buildNetFacesFromSolutionFaces(solutionFaces);

    expectedNetFaces.forEach((face, index) => {
        if (!facesEqual(face, level.netFaces[index])) {
            throw new Error(`netFaces[${index}] does not match answers.solutionFaces in ${level.sourceFile}`);
        }
    });
}

function validateTemplateFacesAgainstNet(level, templateFaces, requiredSlots) {
    const expectedTemplate = buildReconstructionTemplateFaces(level.netFaces, requiredSlots);

    FACE_KEYS.forEach((slotKey) => {
        if (!facesEqual(templateFaces[slotKey], expectedTemplate[slotKey])) {
            throw new Error(`answers.solutionFaces mismatch for ${slotKey} in ${level.sourceFile}`);
        }
    });
}

function validateForwardLevel(level, rawLevel) {
    if (!rawLevel.answers || !Array.isArray(rawLevel.answers.bottomFaces)) {
        throw new Error(`Forward level must declare answers.bottomFaces in ${level.sourceFile}`);
    }

    const expectedBottomFaces = buildBottomFaces(level);
    const suppliedBottomFaces = normalizeFaceSequence(rawLevel.answers.bottomFaces, 'answers.bottomFaces', normalizeBottomFace);

    if (suppliedBottomFaces.length !== expectedBottomFaces.length) {
        throw new Error(`Forward answers.bottomFaces length mismatch in ${level.sourceFile}`);
    }

    suppliedBottomFaces.forEach((face, index) => {
        if (!bottomFacesEqual(face, expectedBottomFaces[index])) {
            throw new Error(`Forward bottom face mismatch at step ${index} in ${level.sourceFile}`);
        }
    });

    return {
        ...level,
        answers: {
            bottomFaces: expectedBottomFaces
        },
        gtBottomFaces: expectedBottomFaces
    };
}

function validateReverseLevel(level, rawLevel) {
    if (!rawLevel.answers || !Array.isArray(rawLevel.answers.bottomFaces)) {
        throw new Error(`Reverse level must declare answers.bottomFaces in ${level.sourceFile}`);
    }

    if (!rawLevel.targets || !Array.isArray(rawLevel.targets.patternSequence)) {
        throw new Error(`Reverse level must declare targets.patternSequence in ${level.sourceFile}`);
    }

    const expectedBottomFaces = buildBottomFaces(level);
    const suppliedBottomFaces = normalizeFaceSequence(rawLevel.answers.bottomFaces, 'answers.bottomFaces', normalizeBottomFace);
    if (suppliedBottomFaces.length !== expectedBottomFaces.length) {
        throw new Error(`Reverse answers.bottomFaces length mismatch in ${level.sourceFile}`);
    }

    suppliedBottomFaces.forEach((face, index) => {
        if (!bottomFacesEqual(face, expectedBottomFaces[index])) {
            throw new Error(`Reverse bottom face mismatch at step ${index} in ${level.sourceFile}`);
        }
    });

    const expectedPatternSequence = expectedBottomFaces.slice(1).map((face) => face.patternId);
    if (rawLevel.targets.patternSequence.length !== expectedPatternSequence.length) {
        throw new Error(`Reverse targets.patternSequence length mismatch in ${level.sourceFile}`);
    }

    rawLevel.targets.patternSequence.forEach((patternId, index) => {
        if (patternId !== expectedPatternSequence[index]) {
            throw new Error(`Reverse target mismatch at step ${index + 1} in ${level.sourceFile}`);
        }
    });

    return {
        ...level,
        answers: {
            bottomFaces: expectedBottomFaces
        },
        targets: {
            patternSequence: expectedPatternSequence
        },
        gtBottomFaces: expectedBottomFaces,
        gtPatternSequence: expectedPatternSequence
    };
}

function validateReconstructLevel(level, rawLevel) {
    if (!rawLevel.answers || !rawLevel.answers.solutionFaces) {
        throw new Error(`Reconstruct level must declare answers.solutionFaces in ${level.sourceFile}`);
    }

    if (!rawLevel.answers.trueSolutionFaces) {
        throw new Error(`Reconstruct level must declare answers.trueSolutionFaces in ${level.sourceFile}`);
    }

    if (!Array.isArray(rawLevel.answers.bottomFaces)) {
        throw new Error(`Reconstruct level must declare answers.bottomFaces in ${level.sourceFile}`);
    }

    if (!rawLevel.prompt || typeof rawLevel.prompt !== 'object') {
        throw new Error(`Reconstruct level must declare prompt data in ${level.sourceFile}`);
    }

    if (!Array.isArray(rawLevel.prompt.directions)) {
        throw new Error(`Reconstruct level must declare prompt.directions in ${level.sourceFile}`);
    }

    const rawObservedPathFaces = rawLevel.prompt.observedPathFaces ?? rawLevel.prompt.observedStampFaces;
    if (!Array.isArray(rawObservedPathFaces)) {
        throw new Error(`Reconstruct level must declare prompt.observedPathFaces in ${level.sourceFile}`);
    }

    if (!Array.isArray(rawLevel.prompt.slotSequence)) {
        throw new Error(`Reconstruct level must declare prompt.slotSequence in ${level.sourceFile}`);
    }

    if (!Array.isArray(rawLevel.prompt.requiredSlots)) {
        throw new Error(`Reconstruct level must declare prompt.requiredSlots in ${level.sourceFile}`);
    }

    if (!Number.isFinite(Number(rawLevel.prompt.requiredCount))) {
        throw new Error(`Reconstruct level must declare prompt.requiredCount in ${level.sourceFile}`);
    }

    const solutionFaces = normalizeSolutionFaceMap(rawLevel.answers.solutionFaces);
    const trueSolutionFaces = normalizeSolutionFaceMap(rawLevel.answers.trueSolutionFaces);
    validateNetFacesAgainstSolution(level, trueSolutionFaces);

    const solutionCube = cubeFromSolutionFaces(trueSolutionFaces);
    solutionCube.x = level.startX;
    solutionCube.y = level.startY;

    const expectedBottomFaces = buildBottomFacesFromCube(solutionCube, level.path);
    const expectedPrompt = buildReconstructionPromptFromCube(solutionCube, level.path);
    validateTemplateFacesAgainstNet(level, solutionFaces, expectedPrompt.requiredSlots);

    const suppliedBottomFaces = normalizeFaceSequence(rawLevel.answers.bottomFaces, 'answers.bottomFaces', normalizeBottomFace);
    if (suppliedBottomFaces.length !== expectedBottomFaces.length) {
        throw new Error(`Reconstruct answers.bottomFaces length mismatch in ${level.sourceFile}`);
    }

    suppliedBottomFaces.forEach((face, index) => {
        if (!bottomFacesEqual(face, expectedBottomFaces[index])) {
            throw new Error(`Reconstruct bottom face mismatch at step ${index} in ${level.sourceFile}`);
        }
    });

    const suppliedDirections = normalizePath(rawLevel.prompt.directions, 'prompt.directions');
    if (JSON.stringify(suppliedDirections) !== JSON.stringify(expectedPrompt.directions)) {
        throw new Error(`Reconstruct prompt.directions mismatch in ${level.sourceFile}`);
    }

    const suppliedObserved = normalizeFaceSequence(rawObservedPathFaces, 'prompt.observedPathFaces');
    if (suppliedObserved.length !== expectedPrompt.observedPathFaces.length) {
        throw new Error(`Reconstruct prompt.observedPathFaces length mismatch in ${level.sourceFile}`);
    }

    suppliedObserved.forEach((face, index) => {
        if (!facesEqual(face, expectedPrompt.observedPathFaces[index])) {
            throw new Error(`Reconstruct observed path face mismatch at step ${index + 1} in ${level.sourceFile}`);
        }
    });

    if (JSON.stringify(rawLevel.prompt.slotSequence) !== JSON.stringify(expectedPrompt.slotSequence)) {
        throw new Error(`Reconstruct prompt.slotSequence mismatch in ${level.sourceFile}`);
    }

    if (JSON.stringify(rawLevel.prompt.requiredSlots) !== JSON.stringify(expectedPrompt.requiredSlots)) {
        throw new Error(`Reconstruct prompt.requiredSlots mismatch in ${level.sourceFile}`);
    }

    if (Number(rawLevel.prompt.requiredCount) !== expectedPrompt.requiredCount) {
        throw new Error(`Reconstruct prompt.requiredCount mismatch in ${level.sourceFile}`);
    }

    return {
        ...level,
        answers: {
            solutionFaces,
            trueSolutionFaces,
            bottomFaces: expectedBottomFaces
        },
        prompt: expectedPrompt,
        solutionFaces,
        trueSolutionFaces,
        gtBottomFaces: expectedBottomFaces
    };
}

function validateAndPrepareLevel(rawLevel, fallbackId, mode, sourcePath) {
    const baseLevel = ensureBaseLevel(rawLevel, fallbackId, mode, sourcePath);

    switch (mode) {
        case 'forward':
            return validateForwardLevel(baseLevel, rawLevel);
        case 'reverse':
            return validateReverseLevel(baseLevel, rawLevel);
        case 'reconstruct':
            return validateReconstructLevel(baseLevel, rawLevel);
        default:
            throw new Error(`Unsupported mode: ${mode}`);
    }
}

function readModeDirectory(mode) {
    const modeDir = path.join(LEVELS_ROOT, mode);
    if (!fs.existsSync(modeDir)) {
        return [];
    }

    return fs.readdirSync(modeDir)
        .filter((fileName) => fileName.endsWith('.json'))
        .sort((a, b) => a.localeCompare(b))
        .map((fileName) => path.join(modeDir, fileName));
}

function collectCatalogFromDisk() {
    ensureLevelRoot();

    const modes = {};

    MODE_KEYS.forEach((mode) => {
        const levels = readModeDirectory(mode)
            .map((filePath, index) => {
                const rawLevel = JSON.parse(fs.readFileSync(filePath, 'utf8'));
                return validateAndPrepareLevel(rawLevel, index + 1, mode, filePath);
            })
            .sort(sortLevels);

        modes[mode] = {
            groups: buildDefaultGroups(levels),
            levels
        };
    });

    return {
        version: 3,
        generatedAt: new Date().toISOString(),
        modes
    };
}

function writeCatalogAssets(catalog) {
    ensureLevelRoot();
    fs.writeFileSync(CATALOG_JSON_PATH, `${JSON.stringify(catalog, null, 2)}\n`, 'utf8');
    fs.writeFileSync(
        CATALOG_JS_PATH,
        `window.__LEVEL_CATALOG_FALLBACK__ = ${JSON.stringify(catalog, null, 2)};\n`,
        'utf8'
    );
}

function removeMatchingFiles(mode, matcher) {
    const modeDir = path.join(LEVELS_ROOT, mode);
    if (!fs.existsSync(modeDir)) {
        return;
    }

    fs.readdirSync(modeDir).forEach((fileName) => {
        if (matcher(fileName)) {
            fs.unlinkSync(path.join(modeDir, fileName));
        }
    });
}

module.exports = {
    MODE_KEYS,
    LEVELS_ROOT,
    CATALOG_JSON_PATH,
    CATALOG_JS_PATH,
    inferDifficultyFromMoves,
    computeBoard,
    buildSolutionFaces,
    buildBottomFaces,
    buildReverseTargets,
    buildReconstructionPrompt,
    buildReconstructionPromptFromCube,
    buildDefaultGroups,
    ensureLevelRoot,
    validateAndPrepareLevel,
    collectCatalogFromDisk,
    writeCatalogAssets,
    removeMatchingFiles
};
