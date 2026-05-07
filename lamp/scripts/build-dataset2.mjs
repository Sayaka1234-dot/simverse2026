import { execFile } from 'node:child_process';
import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';
import { buildDatasetArtifacts } from './build-dataset.mjs';
import {
  buildCaptureUrl,
  buildImageOutputPath,
  decodeCanvasImageDataUrl,
  extractCanvasImageDataUrl
} from './lib/capture-config.mjs';

const execFileAsync = promisify(execFile);

const filePath = fileURLToPath(import.meta.url);
const scriptsDir = path.dirname(filePath);
const projectRoot = path.resolve(scriptsDir, '..');
const levels2Dir = path.join(projectRoot, 'levels2');
const task2Dir = path.join(projectRoot, 'task2');
const image2Dir = path.join(projectRoot, 'image2');

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

async function readLevelSet() {
  const manifest = JSON.parse(await fs.readFile(path.join(levels2Dir, 'manifest.json'), 'utf8'));
  const levels = await Promise.all(
    manifest.levels.map(async (fileName) =>
      JSON.parse(await fs.readFile(path.join(levels2Dir, fileName), 'utf8'))
    )
  );

  return { manifest, levels };
}

async function collectExistingSampleIds(directory, extension) {
  try {
    const entries = await fs.readdir(directory, { withFileTypes: true });
    return new Set(
      entries
        .filter((entry) => entry.isFile() && entry.name.startsWith('level_') && entry.name.endsWith(extension))
        .map((entry) => path.basename(entry.name, extension))
    );
  } catch (error) {
    if (error?.code === 'ENOENT') {
      return new Set();
    }
    throw error;
  }
}

export function partitionPendingSamples({ tasks, existingTaskIds = new Set(), existingImageIds = new Set() }) {
  return {
    pendingTasks: tasks.filter((task) => !existingTaskIds.has(task.sample_id)),
    pendingImages: tasks.filter((task) => !existingImageIds.has(task.sample_id))
  };
}

async function writeTaskArtifacts({ tasks, manifestRows }) {
  await fs.mkdir(task2Dir, { recursive: true });
  await fs.mkdir(image2Dir, { recursive: true });

  await Promise.all(
    tasks.map((task) =>
      fs.writeFile(
        path.join(task2Dir, `${task.sample_id}.json`),
        JSON.stringify(task, null, 2)
      )
    )
  );

  await fs.writeFile(
    path.join(task2Dir, 'manifest.jsonl'),
    `${manifestRows.map((row) => JSON.stringify(row)).join('\n')}\n`
  );
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

async function captureLevelImage({ edgeExecutable, baseUrl, levelFile, levelId }) {
  const outputPath = buildImageOutputPath({
    imagesDir: image2Dir,
    levelId
  });
  const captureUrl = buildCaptureUrl({
    baseUrl,
    levelFile
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

async function capturePendingImages({ pendingImages }) {
  if (pendingImages.length === 0) {
    return;
  }

  const edgeExecutable = await resolveEdgeExecutable();
  const server = await startStaticServer({ rootDir: projectRoot });

  try {
    for (const task of pendingImages) {
      await captureLevelImage({
        edgeExecutable,
        baseUrl: server.baseUrl,
        levelFile: `levels2/${task.sample_id}.json`,
        levelId: task.sample_id
      });
    }
  } finally {
    await server.close();
  }
}

async function writeMatchingRandomSelection() {
  const sourceCandidates = [
    { path: path.join(projectRoot, 'eval-thinking', 'random_50_tasks.json'), needsTransform: true },
    { path: path.join(projectRoot, 'eval', 'random_50_tasks.json'), needsTransform: true },
    { path: path.join(projectRoot, 'eval-thinking', 'random_50_tasks2.json'), needsTransform: false },
    { path: path.join(projectRoot, 'eval', 'random_50_tasks2.json'), needsTransform: false }
  ];

  let transformed = null;

  for (const candidate of sourceCandidates) {
    try {
      const selectionText = (await fs.readFile(candidate.path, 'utf8')).replace(/^\uFEFF/, '');
      const rawSelection = JSON.parse(selectionText);
      transformed = candidate.needsTransform
        ? {
            ...rawSelection,
            subset_name: 'random_50_tasks2',
            source_manifest: 'task2/manifest.jsonl',
            samples: rawSelection.samples.map((sample) => ({
              ...sample,
              task_path: sample.task_path.replace(/^task\//, 'task2/'),
              image: sample.image.replace(/^images\//, 'image2/')
            }))
          }
        : rawSelection;
      break;
    } catch (error) {
      if (error?.code !== 'ENOENT') {
        throw error;
      }
    }
  }

  if (!transformed) {
    return;
  }

  const targets = [
    path.join(projectRoot, 'eval-thinking', 'random_50_tasks2.json'),
    path.join(projectRoot, 'eval', 'random_50_tasks2.json')
  ];

  await Promise.all(targets.map((target) => fs.writeFile(target, JSON.stringify(transformed, null, 2))));
}

async function main() {
  const { levels } = await readLevelSet();
  const { tasks, manifestRows } = buildDatasetArtifacts({
    levels,
    levelDirName: 'levels2',
    taskDirName: 'task2',
    imageDirName: 'image2',
    taskType: 'mechanical_lamp_targeting_with_walls'
  });
  const existingTaskIds = await collectExistingSampleIds(task2Dir, '.json');
  const existingImageIds = await collectExistingSampleIds(image2Dir, '.png');
  const { pendingTasks, pendingImages } = partitionPendingSamples({
    tasks,
    existingTaskIds,
    existingImageIds
  });

  await writeTaskArtifacts({ tasks: pendingTasks, manifestRows });
  await capturePendingImages({ pendingImages });
  await writeMatchingRandomSelection();
}

if (process.argv[1] && path.resolve(process.argv[1]) === filePath) {
  main().catch((error) => {
    console.error(error);
    process.exit(1);
  });
}
