import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { solveTarget } from './lib/kinematics.mjs';
import { assertLevelWritable } from './lib/level-schema.mjs';
import { pickRandom, repeat } from './lib/random.mjs';

const filePath = fileURLToPath(import.meta.url);
const scriptsDir = path.dirname(filePath);
const levelsDir = path.resolve(scriptsDir, '../levels');
const workspace = {
  width: 800,
  height: 600,
  gridSize: 40
};
const SEGMENT_CHOICES = [2, 3, 4, 5];
const LENGTH_CHOICES = [50, 70, 90, 110];
const ANGLE_STEP = 5;
const LIGHT_RADIUS = 24;
const ANGLE_CHOICES = Array.from(
  { length: ((180 - (-180)) / ANGLE_STEP) + 1 },
  (_, index) => -180 + (index * ANGLE_STEP)
);
const ORIGIN_CHOICES = [
  { x: 80, y: 440 },
  { x: 80, y: 480 },
  { x: 80, y: 520 },
  { x: 120, y: 440 },
  { x: 120, y: 480 },
  { x: 120, y: 520 },
  { x: 160, y: 480 },
  { x: 160, y: 520 }
];
const ARM_BASE_OFFSET_CHOICES = [
  { x: -120, y: -120 },
  { x: -120, y: -80 },
  { x: -120, y: -40 },
  { x: -120, y: 0 },
  { x: -120, y: 40 },
  { x: -120, y: 80 },
  { x: -120, y: 120 },
  { x: -80, y: -120 },
  { x: -80, y: -80 },
  { x: -80, y: -40 },
  { x: -80, y: 0 },
  { x: -80, y: 40 },
  { x: -80, y: 80 },
  { x: -80, y: 120 },
  { x: -40, y: -120 },
  { x: -40, y: -80 },
  { x: -40, y: -40 },
  { x: -40, y: 0 },
  { x: -40, y: 40 },
  { x: -40, y: 80 },
  { x: -40, y: 120 },
  { x: 0, y: -120 },
  { x: 0, y: -80 },
  { x: 0, y: -40 },
  { x: 0, y: 0 },
  { x: 0, y: 40 },
  { x: 0, y: 80 },
  { x: 0, y: 120 },
  { x: 40, y: -120 },
  { x: 40, y: -80 },
  { x: 40, y: -40 },
  { x: 40, y: 0 },
  { x: 40, y: 40 },
  { x: 40, y: 80 },
  { x: 40, y: 120 },
  { x: 80, y: -120 },
  { x: 80, y: -80 },
  { x: 80, y: -40 },
  { x: 80, y: 0 },
  { x: 80, y: 40 },
  { x: 80, y: 80 },
  { x: 80, y: 120 },
  { x: 120, y: -120 },
  { x: 120, y: -80 },
  { x: 120, y: -40 },
  { x: 120, y: 0 },
  { x: 120, y: 40 },
  { x: 120, y: 80 },
  { x: 120, y: 120 }
];

function createWorkspace(origin) {
  return {
    ...workspace,
    origin
  };
}

export function generateLevel({ id, segmentCount, lengths, solutionAngles, origin = ORIGIN_CHOICES[0], armBaseOffset = { x: 0, y: 0 } }) {
  const relativeTarget = solveTarget(lengths, solutionAngles);
  const target = {
    x: Number((armBaseOffset.x + relativeTarget.x).toFixed(2)),
    y: Number((armBaseOffset.y + relativeTarget.y).toFixed(2))
  };

  return assertLevelWritable({
    id,
    difficulty: segmentCount,
    workspace: createWorkspace(origin),
    lamp: { lightRadius: LIGHT_RADIUS },
    arm: {
      segmentCount,
      segments: lengths.map((length) => ({ length })),
      initialAngles: repeat(segmentCount, () => 0),
      solutionAngles,
      angleStep: ANGLE_STEP,
      angleMin: -180,
      angleMax: 180
    },
    armBaseOffset,
    target,
    meta: { showDebugInfo: true }
  });
}

export function generateRandomLevel({ id, random = Math.random }) {
  for (let attempt = 0; attempt < 1000; attempt += 1) {
    const segmentCount = pickRandom(SEGMENT_CHOICES, random);
    const lengths = repeat(segmentCount, () => pickRandom(LENGTH_CHOICES, random));
    const solutionAngles = repeat(segmentCount, () => pickRandom(ANGLE_CHOICES, random));
    const origin = pickRandom(ORIGIN_CHOICES, random);
    const armBaseOffset = pickRandom(ARM_BASE_OFFSET_CHOICES, random);

    try {
      return generateLevel({
        id,
        segmentCount,
        lengths,
        solutionAngles,
        origin,
        armBaseOffset
      });
    } catch {
      continue;
    }
  }

  throw new Error(`Unable to generate a valid level for ${id}`);
}

export function createLevelSet({ count = 202, random = Math.random }) {
  return repeat(count, (index) =>
    generateRandomLevel({
      id: `level_${String(index + 1).padStart(3, '0')}`,
      random
    })
  );
}

export async function writeLevelSet(levels) {
  await fs.mkdir(levelsDir, { recursive: true });
  await fs.writeFile(
    path.join(levelsDir, 'manifest.json'),
    JSON.stringify({ levels: levels.map((level) => `${level.id}.json`) }, null, 2)
  );

  await Promise.all(
    levels.map((level) =>
      fs.writeFile(path.join(levelsDir, `${level.id}.json`), JSON.stringify(level, null, 2))
    )
  );
}

async function main() {
  const levels = createLevelSet({});

  await writeLevelSet(levels);
}

if (process.argv[1] && path.resolve(process.argv[1]) === filePath) {
  main().catch((error) => {
    console.error(error);
    process.exit(1);
  });
}

