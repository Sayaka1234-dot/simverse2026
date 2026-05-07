import { loadLevel } from './core/level-loader.js';
import { computeArmChain } from './core/kinematics.js';
import { renderFrame } from './render/canvas-renderer.js';
import { computeCoverage } from './core/win-checker.js';

async function main() {
  const params = new URLSearchParams(window.location.search);
  const levelFile = params.get('level');
  const exportMode = params.get('export');
  const canvas = document.getElementById('capture-canvas');
  const captureOutput = document.getElementById('capture-output');

  if (!levelFile) {
    throw new Error('Missing level query parameter');
  }

  const level = await loadLevel(levelFile);
  const armBaseOffset = level.armBaseOffset || { x: 0, y: 0 };
  const chain = computeArmChain({
    origin: armBaseOffset,
    segments: level.arm.segments,
    angles: level.arm.initialAngles
  });
  const coverage = computeCoverage({
    target: level.target,
    bulb: chain.bulb,
    lightRadius: level.lamp.lightRadius
  });
  const ctx = canvas.getContext('2d');

  renderFrame(ctx, { level, chain, coverage });

  if (exportMode === 'png' && captureOutput) {
    captureOutput.textContent = canvas.toDataURL('image/png');
  }

  document.body.dataset.captureReady = 'true';
  window.__CAPTURE_READY__ = true;
}

main().catch((error) => {
  console.error(error);
  document.body.dataset.captureReady = 'error';
});
