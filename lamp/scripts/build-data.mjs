import { execFile } from 'node:child_process';
import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';
import {
  buildCaptureUrl,
  buildImageOutputPath,
  decodeCanvasImageDataUrl,
  extractCanvasImageDataUrl
} from './lib/capture-config.mjs';
import { createObstacleVariantLevelSet, writeLevelSet } from './generate-levels2.mjs';

const execFileAsync = promisify(execFile);
const filePath = fileURLToPath(import.meta.url);
const scriptsDir = path.dirname(filePath);
const projectRoot = path.resolve(scriptsDir, '..');
const levels2Dir = path.join(projectRoot, 'levels2');
const task2Dir = path.join(projectRoot, 'task2');
const image2Dir = path.join(projectRoot, 'image2');
const dataDir = path.join(projectRoot, 'data');
const dataLevelsDir = path.join(dataDir, 'levels');
const dataImagesDir = path.join(dataDir, 'images');

export const DATASET_LIMIT = 610;

function getContentType(filePathname) {
  const extension = path.extname(filePathname).toLowerCase();
  const contentTypes = {
    '.css': 'text/css; charset=utf-8',
    '.html': 'text/html; charset=utf-8',
    '.js': 'text/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.png': 'image/png'
  };

  return contentTypes[extension] ?? 'application/octet-stream';
}

function resolveRequestPath(rootDir, requestUrl) {
  const url = new URL(requestUrl, 'http://127.0.0.1');
  const pathname = url.pathname === '/' ? '/capture.html' : url.pathname;
  const resolved = path.resolve(rootDir, `.${pathname}`);

  if (!resolved.startsWith(rootDir)) {
    throw new Error(`Refusing to serve path outside root: ${pathname}`);
  }

  return resolved;
}

async function startStaticServer({ rootDir }) {
  const server = http.createServer(async (request, response) => {
    try {
      const filePathname = resolveRequestPath(rootDir, request.url);
      const buffer = await fs.readFile(filePathname);

      response.writeHead(200, { 'Content-Type': getContentType(filePathname) });
      response.end(buffer);
    } catch (error) {
      const statusCode = error.code === 'ENOENT' ? 404 : 500;
      response.writeHead(statusCode, { 'Content-Type': 'text/plain; charset=utf-8' });
      response.end(statusCode === 404 ? 'Not found' : String(error.message ?? error));
    }
  });

  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const address = server.address();

  return {
    baseUrl: `http://127.0.0.1:${address.port}`,
    async close() {
      await new Promise((resolve, reject) => server.close((error) => (error ? reject(error) : resolve())));
    }
  };
}

async function resolveEdgeExecutable() {
  const candidates = [
    process.env.EDGE_PATH,
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe'
  ].filter(Boolean);

  for (const candidate of candidates) {
    try {
      await fs.access(candidate);
      return candidate;
    } catch {
      continue;
    }
  }

  throw new Error('Unable to locate a Microsoft Edge executable. Set EDGE_PATH to continue.');
}

async function ensureLevels2Source() {
  try {
    const manifest = JSON.parse(await fs.readFile(path.join(levels2Dir, 'manifest.json'), 'utf8'));
    if (Array.isArray(manifest.levels) && manifest.levels.length >= DATASET_LIMIT) {
      return;
    }
  } catch (error) {
    if (error?.code !== 'ENOENT') {
      throw error;
    }
  }

  const { levels } = await createObstacleVariantLevelSet({
    targetCount: DATASET_LIMIT,
    preserveExisting: true
  });
  await writeLevelSet(levels);
}

async function readLevelSet() {
  const manifest = JSON.parse(await fs.readFile(path.join(levels2Dir, 'manifest.json'), 'utf8'));
  const selectedFiles = manifest.levels.slice(0, DATASET_LIMIT);
  const levels = await Promise.all(
    selectedFiles.map(async (fileName) =>
      JSON.parse(await fs.readFile(path.join(levels2Dir, fileName), 'utf8'))
    )
  );

  return levels;
}

function buildSequentialExportId(index) {
  return `lamp-${String(index).padStart(3, '0')}`;
}

export function buildExportLevel({ level, exportId }) {
  const { arm, ...rest } = structuredClone(level);
  const { solutionAngles, ...armRest } = arm;

  return {
    ...rest,
    id: exportId,
    arm: {
      ...armRest,
      answer: solutionAngles
    }
  };
}

export function buildExportEntries({ levels }) {
  return levels.slice(0, DATASET_LIMIT).map((level, index) => {
    const exportId = buildSequentialExportId(index);
    return {
      sourceId: level.id,
      exportId,
      level: buildExportLevel({ level, exportId })
    };
  });
}

async function resetDataDirectories() {
  await fs.rm(dataDir, { recursive: true, force: true });
  await fs.mkdir(dataLevelsDir, { recursive: true });
  await fs.mkdir(dataImagesDir, { recursive: true });
}

async function writeExportLevels(entries) {
  await Promise.all(
    entries.map((entry) =>
      fs.writeFile(
        path.join(dataLevelsDir, `${entry.exportId}.json`),
        JSON.stringify(entry.level, null, 2)
      )
    )
  );
}

async function captureExportImage({ edgeExecutable, baseUrl, sourceId, exportId }) {
  const outputPath = buildImageOutputPath({
    imagesDir: dataImagesDir,
    levelId: exportId
  });
  const captureUrl = buildCaptureUrl({
    baseUrl,
    levelFile: `levels2/${sourceId}.json`
  });

  const { stdout } = await execFileAsync(edgeExecutable, [
    '--headless',
    '--disable-gpu',
    '--virtual-time-budget=3000',
    '--dump-dom',
    captureUrl
  ]);

  const imageDataUrl = extractCanvasImageDataUrl(stdout);
  const imageBuffer = decodeCanvasImageDataUrl(imageDataUrl);

  await fs.writeFile(outputPath, imageBuffer);
}

async function writeExportImages(entries) {
  const edgeExecutable = await resolveEdgeExecutable();
  const server = await startStaticServer({ rootDir: projectRoot });

  try {
    for (const entry of entries) {
      await captureExportImage({
        edgeExecutable,
        baseUrl: server.baseUrl,
        sourceId: entry.sourceId,
        exportId: entry.exportId
      });
    }
  } finally {
    await server.close();
  }
}

async function cleanupIntermediateDirectories() {
  await fs.rm(levels2Dir, { recursive: true, force: true });
  await fs.rm(task2Dir, { recursive: true, force: true });
  await fs.rm(image2Dir, { recursive: true, force: true });
}

export async function buildDataExport() {
  await ensureLevels2Source();
  const levels = await readLevelSet();
  const entries = buildExportEntries({ levels });
  await resetDataDirectories();
  await writeExportLevels(entries);
  await writeExportImages(entries);
  await cleanupIntermediateDirectories();
}

if (process.argv[1] && path.resolve(process.argv[1]) === filePath) {
  buildDataExport().catch((error) => {
    console.error(error);
    process.exit(1);
  });
}
