// SimVerse v1: levels live at /data/levels/<file>.json (the canonical dataset
// directory shared by both the frontend and the eval pipeline). Manifest is at
// /data/levels/manifest.json.

function assertLevelShape(level) {
  if (!Array.isArray(level?.arm?.segments)) {
    throw new Error('segments must be an array');
  }

  if (level.arm.segmentCount !== level.arm.segments.length) {
    throw new Error('segmentCount mismatch');
  }

  if (level.arm.initialAngles.length !== level.arm.segmentCount) {
    throw new Error('initialAngles length mismatch');
  }

  // SimVerse v1: gold answer moved to top-level `answer.actions`.
  // Legacy `arm.solutionAngles` field is gone — check the new schema instead.
  const actions = level?.answer?.actions;
  if (!Array.isArray(actions) || actions.length !== level.arm.segmentCount) {
    throw new Error('answer.actions length mismatch with segmentCount');
  }

  return level;
}

async function loadJson(path) {
  const response = await fetch(path);

  if (!response.ok) {
    throw new Error(`Failed to load ${path}`);
  }

  return response.json();
}

function resolveLevelPath(fileName) {
  if (fileName.includes('/')) {
    return fileName.startsWith('/') ? fileName : `/${fileName}`;
  }

  return `/data/levels/${fileName}`;
}

export async function loadManifest() {
  const manifest = await loadJson('/data/levels/manifest.json');

  return manifest.levels;
}

export async function loadLevel(fileName) {
  const level = await loadJson(resolveLevelPath(fileName));

  return assertLevelShape(level);
}
