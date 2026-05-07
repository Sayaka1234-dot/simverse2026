import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { buildObstacleVariantLevel as buildObstacleVariantLevelImpl } from './lib/obstacle-utils.mjs';
import { assertLevelWritable } from './lib/level-schema.mjs';
import { generateRandomLevel } from './generate-levels.mjs';

const filePath = fileURLToPath(import.meta.url);
const scriptsDir = path.dirname(filePath);
const projectRoot = path.resolve(scriptsDir, '..');
const levelsDir = path.join(projectRoot, 'levels');
const levels2Dir = path.join(projectRoot, 'levels2');

function createSeededRandom(seedText) {
  let seed = 2166136261;

  for (const character of seedText) {
    seed ^= character.charCodeAt(0);
    seed = Math.imul(seed, 16777619);
  }

  return function random() {
    seed += 0x6D2B79F5;
    let value = seed;
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
}

async function readLevelSet() {
  const manifest = JSON.parse(await fs.readFile(path.join(levelsDir, 'manifest.json'), 'utf8'));
  const levels = await Promise.all(
    manifest.levels.map(async (fileName) =>
      JSON.parse(await fs.readFile(path.join(levelsDir, fileName), 'utf8'))
    )
  );

  return { manifest, levels };
}

async function readExistingLevelSet() {
  try {
    const manifest = JSON.parse(await fs.readFile(path.join(levels2Dir, 'manifest.json'), 'utf8'));
    const levels = await Promise.all(
      manifest.levels.map(async (fileName) =>
        JSON.parse(await fs.readFile(path.join(levels2Dir, fileName), 'utf8'))
      )
    );

    return { manifest, levels };
  } catch (error) {
    if (error?.code === 'ENOENT') {
      return { manifest: { levels: [] }, levels: [] };
    }
    throw error;
  }
}

export function extendObstacleVariantLevels({ existingLevels = [], targetCount = existingLevels.length }) {
  const levelsById = new Map(existingLevels.map((level) => [level.id, level]));
  const expanded = [...existingLevels];

  for (let index = 1; index <= targetCount; index += 1) {
    const id = `level_${String(index).padStart(3, '0')}`;
    if (levelsById.has(id)) {
      continue;
    }

    const baseLevel = generateRandomLevel({
      id,
      random: createSeededRandom(`${id}:base:v1`)
    });
    const withObstacles = buildObstacleVariantLevelImpl({
      level: baseLevel,
      random: createSeededRandom(`${id}:walls:v1`)
    });
    const normalized = assertLevelWritable(withObstacles);

    expanded.push(normalized);
    levelsById.set(id, normalized);
  }

  return expanded.sort((left, right) => left.id.localeCompare(right.id));
}

export async function createObstacleVariantLevelSet({ targetCount, preserveExisting = false } = {}) {
  if (preserveExisting) {
    const { levels: existingLevels } = await readExistingLevelSet();
    const levels = extendObstacleVariantLevels({
      existingLevels,
      targetCount: targetCount ?? existingLevels.length
    });

    return {
      manifest: { levels: levels.map((level) => `${level.id}.json`) },
      levels
    };
  }

  const { manifest, levels } = await readLevelSet();
  const generatedLevels = levels.map((level) => {
    const withObstacles = buildObstacleVariantLevelImpl({
      level,
      random: createSeededRandom(`${level.id}:walls:v1`)
    });

    return assertLevelWritable(withObstacles);
  });

  return {
    manifest,
    levels: generatedLevels
  };
}

export function buildObstacleVariantLevel(options) {
  return buildObstacleVariantLevelImpl(options);
}

export async function writeLevelSet(levels, { preserveExistingFiles = false } = {}) {
  await fs.mkdir(levels2Dir, { recursive: true });
  await fs.writeFile(
    path.join(levels2Dir, 'manifest.json'),
    JSON.stringify({ levels: levels.map((level) => `${level.id}.json`) }, null, 2)
  );

  if (!preserveExistingFiles) {
    await Promise.all(
      levels.map((level) =>
        fs.writeFile(path.join(levels2Dir, `${level.id}.json`), JSON.stringify(level, null, 2))
      )
    );
    return;
  }

  await Promise.all(
    levels.map(async (level) => {
      const targetPath = path.join(levels2Dir, `${level.id}.json`);
      try {
        await fs.access(targetPath);
        return;
      } catch (error) {
        if (error?.code !== 'ENOENT') {
          throw error;
        }
      }

      await fs.writeFile(targetPath, JSON.stringify(level, null, 2));
    })
  );
}

async function main() {
  const targetCountFlagIndex = process.argv.indexOf('--target-count');
  const targetCount = targetCountFlagIndex >= 0
    ? Number.parseInt(process.argv[targetCountFlagIndex + 1] ?? '', 10)
    : undefined;
  const preserveExisting = process.argv.includes('--preserve-existing');
  const { levels } = await createObstacleVariantLevelSet({
    targetCount: Number.isFinite(targetCount) ? targetCount : undefined,
    preserveExisting
  });
  await writeLevelSet(levels, { preserveExistingFiles: preserveExisting });
}

if (process.argv[1] && path.resolve(process.argv[1]) === filePath) {
  main().catch((error) => {
    console.error(error);
    process.exit(1);
  });
}
