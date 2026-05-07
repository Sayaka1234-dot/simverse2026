import { execFile } from 'node:child_process';
import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';
import { buildManifestRows, buildTaskPayload, serializeManifestRows } from './lib/dataset-schema.mjs';
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

async function readLevelSet({ levelsDir }) {
  const manifest = JSON.parse(await fs.readFile(path.join(levelsDir, 'manifest.json'), 'utf8'));

  const levels = await Promise.all(
    manifest.levels.map(async (fileName) =>
      JSON.parse(await fs.readFile(path.join(levelsDir, fileName), 'utf8'))
    )
  );

  return { manifest, levels };
}

export function buildDatasetArtifacts({
  levels,
  imageDirName = 'images',
  levelDirName = 'levels',
  taskDirName = 'task',
  taskType = 'mechanical_lamp_targeting'
}) {
  const tasks = levels.map((level) =>
    buildTaskPayload({
      level,
      imageDirName,
      levelDirName,
      taskType
    })
  );
  const manifestRows = buildManifestRows({ tasks, taskDirName });

  return { tasks, manifestRows };
}

async function writeDatasetArtifacts({ tasks, manifestRows, taskDir, imagesDir }) {
  await fs.mkdir(taskDir, { recursive: true });
  await fs.mkdir(imagesDir, { recursive: true });

  await Promise.all(
    tasks.map((task) =>
      fs.writeFile(
        path.join(taskDir, `${task.sample_id}.json`),
        JSON.stringify(task, null, 2)
      )
    )
  );

  await fs.writeFile(path.join(taskDir, 'manifest.jsonl'), serializeManifestRows(manifestRows));
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

async function captureLevelImage({ edgeExecutable, baseUrl, levelFile, levelId, imagesDir }) {
  const outputPath = buildImageOutputPath({
    imagesDir,
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

async function captureImages({ manifest, imagesDir, levelDirName }) {
  const edgeExecutable = await resolveEdgeExecutable();
  const server = await startStaticServer({ rootDir: projectRoot });

  try {
    for (const fileName of manifest.levels) {
      const levelId = path.basename(fileName, '.json');
      await captureLevelImage({
        edgeExecutable,
        baseUrl: server.baseUrl,
        levelFile: `${levelDirName}/${fileName}`,
        levelId,
        imagesDir
      });
    }
  } finally {
    await server.close();
  }
}

export async function buildDataset({
  levelDirName = 'levels',
  taskDirName = 'task',
  imageDirName = 'images',
  taskType = 'mechanical_lamp_targeting'
} = {}) {
  const levelsDir = path.join(projectRoot, levelDirName);
  const taskDir = path.join(projectRoot, taskDirName);
  const imagesDir = path.join(projectRoot, imageDirName);
  const { manifest, levels } = await readLevelSet({ levelsDir });
  const { tasks, manifestRows } = buildDatasetArtifacts({
    levels,
    imageDirName,
    levelDirName,
    taskDirName,
    taskType
  });

  await writeDatasetArtifacts({ tasks, manifestRows, taskDir, imagesDir });
  await captureImages({ manifest, imagesDir, levelDirName });
}

if (process.argv[1] && path.resolve(process.argv[1]) === filePath) {
  buildDataset().catch((error) => {
    console.error(error);
    process.exit(1);
  });
}
