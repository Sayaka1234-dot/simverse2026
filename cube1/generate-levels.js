const fs = require('fs');
const path = require('path');
const {
    LEVELS_ROOT,
    computeBoard,
    ensureLevelRoot,
    collectCatalogFromDisk,
    writeCatalogAssets,
    removeMatchingFiles
} = require('./level-catalog');
const {
    FACE_KEYS,
    cubeFromSolutionFaces,
    buildNetFacesFromSolutionFaces,
    simulatePath,
    simulatePathViewFaces,
    flipFaceSequenceVertically
} = require('./cube-engine');

const DIRS = ['N', 'S', 'E', 'W'];
const ROTATIONS = [0, 90, 180, 270];
const OPPOSITE = { N: 'S', S: 'N', E: 'W', W: 'E' };
const PATTERN_POOL = [
    '1', '2', '3', '4', '5', '6', '7', '8', '9',
    'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M',
    'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
    'smile', 'star', 'heart',
    'arrow_up', 'arrow_right', 'arrow_down', 'arrow_left',
    'circle', 'triangle', 'square', 'diamond', 'plus'
];
const DEFAULT_TOTAL_LEVELS = 502;
const TIER_SPECS = [
    { difficulty: 1, label: 'Difficulty 1', description: '2-3 moves', minMoves: 2, maxMoves: 3 },
    { difficulty: 2, label: 'Difficulty 2', description: '4-5 moves', minMoves: 4, maxMoves: 5 },
    { difficulty: 3, label: 'Difficulty 3', description: '6-7 moves', minMoves: 6, maxMoves: 7 },
    { difficulty: 4, label: 'Difficulty 4', description: '8-9 moves', minMoves: 8, maxMoves: 9 },
    { difficulty: 5, label: 'Difficulty 5', description: '10 moves', minMoves: 10, maxMoves: 10 }
];
const RECONSTRUCTION_SLOT_TO_NET_INDEX = {
    TOP: 0,
    FRONT: 1,
    RIGHT: 2,
    BACK: 3,
    LEFT: 4,
    BOTTOM: 5
};

function mulberry32(seed) {
    let t = seed >>> 0;
    return function rand() {
        t += 0x6D2B79F5;
        let v = Math.imul(t ^ (t >>> 15), t | 1);
        v ^= v + Math.imul(v ^ (v >>> 7), v | 61);
        return ((v ^ (v >>> 14)) >>> 0) / 4294967296;
    };
}

function randInt(rng, min, max) {
    return Math.floor(rng() * (max - min + 1)) + min;
}

function randomItem(items, rng) {
    return items[randInt(rng, 0, items.length - 1)];
}

function weightedChoice(items, rng) {
    const total = items.reduce((sum, item) => sum + item.weight, 0);
    let threshold = rng() * total;

    for (const item of items) {
        threshold -= item.weight;
        if (threshold <= 0) {
            return item.value;
        }
    }

    return items[items.length - 1].value;
}

function stepPosition(position, direction) {
    switch (direction) {
        case 'N': return { x: position.x, y: position.y - 1 };
        case 'S': return { x: position.x, y: position.y + 1 };
        case 'E': return { x: position.x + 1, y: position.y };
        case 'W': return { x: position.x - 1, y: position.y };
        default: return { ...position };
    }
}

function buildRandomPath(moveCount, rng) {
    const pathDirections = [];
    const visited = new Set(['0,0']);
    let current = { x: 0, y: 0 };
    let lastDir = null;

    for (let step = 0; step < moveCount; step += 1) {
        const options = DIRS.map((dir) => {
            const next = stepPosition(current, dir);
            const key = `${next.x},${next.y}`;

            let weight = 1;
            if (lastDir && dir === OPPOSITE[lastDir]) weight -= 0.35;
            if (!visited.has(key)) weight += 0.6;
            if (lastDir && dir !== lastDir && dir !== OPPOSITE[lastDir]) weight += 0.15;

            return { value: dir, weight: Math.max(0.15, weight) };
        });

        const chosen = weightedChoice(options, rng);
        current = stepPosition(current, chosen);
        visited.add(`${current.x},${current.y}`);
        pathDirections.push(chosen);
        lastDir = chosen;
    }

    return pathDirections;
}

function buildSlotTrackingCube() {
    return cubeFromSolutionFaces({
        TOP: { patternId: 'TOP', rotation: 0 },
        BOTTOM: { patternId: 'BOTTOM', rotation: 0 },
        FRONT: { patternId: 'FRONT', rotation: 0 },
        BACK: { patternId: 'BACK', rotation: 0 },
        LEFT: { patternId: 'LEFT', rotation: 0 },
        RIGHT: { patternId: 'RIGHT', rotation: 0 }
    });
}

function hasLongDirectionStreak(pathDirections, streakLength) {
    let streak = 1;
    for (let index = 1; index < pathDirections.length; index += 1) {
        if (pathDirections[index] === pathDirections[index - 1]) {
            streak += 1;
            if (streak >= streakLength) {
                return true;
            }
        } else {
            streak = 1;
        }
    }
    return false;
}

function buildRandomSolutionFaces(rng) {
    while (true) {
        const solutionFaces = {};
        FACE_KEYS.forEach((key) => {
            solutionFaces[key] = {
                patternId: randomItem(PATTERN_POOL, rng),
                rotation: randomItem(ROTATIONS, rng)
            };
        });

        const distinctPatterns = new Set(Object.values(solutionFaces).map((face) => face.patternId)).size;
        if (distinctPatterns >= 3) {
            return solutionFaces;
        }
    }
}

function buildReconstructArtifacts(solutionFaces, pathDirections, board) {
    const cube = cubeFromSolutionFaces(solutionFaces);
    cube.x = board.startX;
    cube.y = board.startY;

    const bottomFaces = simulatePath(cube, pathDirections).map((face) => ({
        patternId: face.patternId,
        rotation: face.rotation,
        x: face.x,
        y: face.y
    }));

    const rawObservedPathFaces = simulatePathViewFaces(cube, pathDirections).slice(1).map((face) => ({
        patternId: face.patternId,
        rotation: face.rotation,
        flipHorizontal: Boolean(face.flipHorizontal),
        flipVertical: Boolean(face.flipVertical)
    }));
    const observedPathFaces = flipFaceSequenceVertically(rawObservedPathFaces);

    const slotSequence = simulatePath(buildSlotTrackingCube(), pathDirections)
        .slice(1)
        .map((face) => face.patternId);
    const requiredSlots = [...new Set(slotSequence)];

    return {
        bottomFaces,
        observedPathFaces,
        slotSequence,
        requiredSlots,
        requiredCount: requiredSlots.length
    };
}

function buildBaseLevel(id, tier, rng) {
    const moveCount = randInt(rng, tier.minMoves, tier.maxMoves);

    for (let attempt = 0; attempt < 500; attempt += 1) {
        const solutionFaces = buildRandomSolutionFaces(rng);
        const pathDirections = buildRandomPath(moveCount, rng);
        const board = computeBoard(pathDirections);
        const netFaces = buildNetFacesFromSolutionFaces(solutionFaces);
        const netPatterns = netFaces.map((face) => face.patternId);
        const artifacts = buildReconstructArtifacts(solutionFaces, pathDirections, board);

        const uniqueCells = new Set(artifacts.bottomFaces.map((face) => `${face.x},${face.y}`)).size;
        const uniqueObserved = new Set(
            artifacts.observedPathFaces.map((face) => `${face.patternId}:${face.rotation}`)
        ).size;
        const distinctRequiredPatterns = new Set(
            artifacts.requiredSlots.map((slotKey) => solutionFaces[slotKey].patternId)
        ).size;

        if (hasLongDirectionStreak(pathDirections, 4)) continue;
        if (uniqueCells < Math.max(2, Math.ceil((moveCount + 1) * 0.5))) continue;
        if (artifacts.requiredCount < Math.max(2, Math.ceil(moveCount / 3))) continue;
        if (uniqueObserved < Math.max(2, Math.ceil(moveCount / 4))) continue;
        if (distinctRequiredPatterns < Math.max(2, Math.ceil(artifacts.requiredCount / 2))) continue;

        return {
            id,
            netLayout: 'standard_cross',
            netFaces,
            netPatterns,
            solutionFaces,
            path: pathDirections,
            startX: board.startX,
            startY: board.startY,
            gridWidth: board.gridWidth,
            gridHeight: board.gridHeight,
            difficulty: tier.difficulty,
            moveCount,
            tier: tier.difficulty,
            tierLabel: tier.label,
            tierDescription: tier.description,
            artifacts
        };
    }

    throw new Error(`Failed to generate a valid level for ${tier.label}`);
}

function buildTiers(totalLevels = DEFAULT_TOTAL_LEVELS) {
    const tierCount = TIER_SPECS.length;
    const baseCount = Math.floor(totalLevels / tierCount);
    const remainder = totalLevels % tierCount;

    return TIER_SPECS.map((tier, index) => ({
        ...tier,
        count: baseCount + (index >= tierCount - remainder ? 1 : 0)
    }));
}

function buildBaseLevels(seed, totalLevels = DEFAULT_TOTAL_LEVELS) {
    const rng = mulberry32(seed);
    const tiers = buildTiers(totalLevels);
    const levels = [];
    const signatures = new Set();

    let nextId = 1;
    for (const tier of tiers) {
        let generated = 0;
        let guard = 0;

        while (generated < tier.count) {
            guard += 1;
            if (guard > 4000) {
                throw new Error(`Generation guard tripped for ${tier.label}`);
            }

            const level = buildBaseLevel(nextId, tier, rng);
            const signature = JSON.stringify({
                netFaces: level.netFaces,
                path: level.path
            });

            if (signatures.has(signature)) {
                continue;
            }

            signatures.add(signature);
            levels.push(level);
            nextId += 1;
            generated += 1;
        }
    }

    return levels;
}

function pickBaseFields(baseLevel, codePrefix, label, index) {
    const ordinal = String(index + 1).padStart(3, '0');

    return {
        id: index + 1,
        code: `${codePrefix}${ordinal}`,
        name: `${label} ${ordinal}`,
        description: `${baseLevel.moveCount}-move ${label.toLowerCase()} puzzle`,
        netLayout: baseLevel.netLayout,
        netFaces: baseLevel.netFaces,
        netPatterns: baseLevel.netPatterns,
        path: baseLevel.path,
        startX: baseLevel.startX,
        startY: baseLevel.startY,
        gridWidth: baseLevel.gridWidth,
        gridHeight: baseLevel.gridHeight,
        difficulty: baseLevel.difficulty,
        moveCount: baseLevel.moveCount,
        tier: baseLevel.tier,
        tierLabel: baseLevel.tierLabel
    };
}

function buildReconstructLevel(baseLevel, index) {
    const solutionFaces = {};
    Object.entries(RECONSTRUCTION_SLOT_TO_NET_INDEX).forEach(([slotKey, netIndex]) => {
        solutionFaces[slotKey] = baseLevel.artifacts.requiredSlots.includes(slotKey)
            ? {
                patternId: baseLevel.netFaces[netIndex].patternId,
                rotation: baseLevel.netFaces[netIndex].rotation
            }
            : {
                patternId: '?',
                rotation: 0
            };
    });

    return {
        ...pickBaseFields(baseLevel, 'C', 'Reconstruct', index),
        answers: {
            solutionFaces,
            trueSolutionFaces: baseLevel.solutionFaces,
            bottomFaces: baseLevel.artifacts.bottomFaces
        },
        prompt: {
            directions: baseLevel.path,
            observedPathFaces: baseLevel.artifacts.observedPathFaces,
            slotSequence: baseLevel.artifacts.slotSequence,
            requiredSlots: baseLevel.artifacts.requiredSlots,
            requiredCount: baseLevel.artifacts.requiredCount
        }
    };
}

function writeModeLevels(mode, levels) {
    const modeDir = path.join(LEVELS_ROOT, mode);
    fs.mkdirSync(modeDir, { recursive: true });
    removeMatchingFiles(mode, (fileName) => fileName.startsWith('generated-') && fileName.endsWith('.json'));

    levels.forEach((level, index) => {
        const filePath = path.join(modeDir, `generated-${String(index + 1).padStart(3, '0')}.json`);
        fs.writeFileSync(filePath, `${JSON.stringify(level, null, 2)}\n`, 'utf8');
    });
}

function main() {
    const seedArg = process.argv.find((arg) => arg.startsWith('--seed='));
    const countArg = process.argv.find((arg) => arg.startsWith('--count='));
    const seed = seedArg ? Number(seedArg.split('=')[1]) : 20260327;
    const totalLevels = countArg ? Number(countArg.split('=')[1]) : DEFAULT_TOTAL_LEVELS;

    ensureLevelRoot();

    const baseLevels = buildBaseLevels(seed, totalLevels);
    writeModeLevels('reconstruct', baseLevels.map(buildReconstructLevel));

    const catalog = collectCatalogFromDisk();
    writeCatalogAssets(catalog);

    console.log(`Generated ${baseLevels.length} base levels with seed ${seed}.`);
    console.log(`Difficulty layers: ${buildTiers(totalLevels).map((tier) => `D${tier.difficulty}=${tier.count}`).join(', ')}`);
    console.log('Rebuilt reconstruct JSON from random cube faces and validated it.');
    console.log('Updated levels/index.json and levels/catalog.generated.js');
}

if (require.main === module) {
    main();
}
