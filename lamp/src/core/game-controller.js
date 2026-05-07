import { createGameState } from './game-state.js';
import { computeArmChain } from './kinematics.js';
import { computeObstacleCollision } from './obstacle-collision.js';
import { computeCoverage } from './win-checker.js';
import { renderAngleControls } from '../ui/angle-controls.js';
import { updateHud } from '../ui/hud.js';
import { renderLevelPanel } from '../ui/level-panel.js';

export function createGameController({ shell, services }) {
  let manifest = [];
  let state = null;
  const ctx =
    shell.canvas.getContext?.('2d') ??
    shell.canvas.getContext?.() ??
    shell.canvas;

  function rerender() {
    const snapshot = state.snapshot();
    const armBaseOffset = snapshot.currentLevel.armBaseOffset || { x: 0, y: 0 };
    const chain = computeArmChain({
      origin: armBaseOffset,
      segments: snapshot.currentLevel.arm.segments,
      angles: snapshot.currentAngles
    });
    const collision = computeObstacleCollision({
      joints: chain.joints,
      obstacles: snapshot.currentLevel.obstacles || []
    });
    const coverage = computeCoverage({
      target: snapshot.currentLevel.target,
      bulb: chain.bulb,
      lightRadius: snapshot.currentLevel.lamp.lightRadius,
      blocked: collision.blocked
    });

    state.markSolved(coverage.solved);
    services.renderFrame(ctx, {
      level: snapshot.currentLevel,
      chain,
      coverage
    });
    renderAngleControls({
      host: shell.controlsHost,
      level: snapshot.currentLevel,
      angles: snapshot.currentAngles,
      onAngleChange: updateAngle
    });
    updateHud(shell.debugList, {
      target: snapshot.currentLevel.target,
      bulb: chain.bulb,
      distance: coverage.distance,
      lightRadius: snapshot.currentLevel.lamp.lightRadius,
      covered: coverage.covered,
      blocked: collision.blocked
    });
    renderLevelPanel({
      host: shell.levelPanel,
      levelIndex: snapshot.currentLevelIndex,
      levelCount: manifest.length,
      solved: coverage.solved,
      onReset: () => {
        state.resetAngles();
        rerender();
      },
      onNext: async () => {
        if (state.snapshot().solved && state.snapshot().currentLevelIndex < manifest.length - 1) {
          state.advanceLevel();
          await loadLevelAt(state.snapshot().currentLevelIndex);
        }
      }
    });
  }

  async function loadLevelAt(index) {
    const level = await services.loadLevel(manifest[index]);

    state.setLevel(level, index);
    rerender();
  }

  function updateAngle(index, angle) {
    state.setAngle(index, angle);
    rerender();
  }

  return {
    async start() {
      manifest = await services.loadManifest();
      state = createGameState({ manifest });
      await loadLevelAt(0);
    },
    updateAngle,
    snapshot() {
      return state.snapshot();
    }
  };
}
