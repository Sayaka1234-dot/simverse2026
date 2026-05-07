export function assertLevelWritable(level) {
  const margin = 40;
  const armBaseOffset = level.armBaseOffset || { x: 0, y: 0 };
  const screenBaseX = level.workspace.origin.x + armBaseOffset.x;
  const screenBaseY = level.workspace.origin.y - armBaseOffset.y;
  const screenTargetX = level.workspace.origin.x + level.target.x;
  const screenTargetY = level.workspace.origin.y - level.target.y;
  const distanceFromBase = Math.hypot(
    level.target.x - armBaseOffset.x,
    level.target.y - armBaseOffset.y
  );

  if (level.workspace.origin.x <= margin || level.workspace.origin.x >= level.workspace.width - margin) {
    throw new Error('origin x is outside the workspace');
  }

  if (level.workspace.origin.y <= margin || level.workspace.origin.y >= level.workspace.height - margin) {
    throw new Error('origin y is outside the workspace');
  }

  if (screenBaseX <= margin || screenBaseX >= level.workspace.width - margin) {
    throw new Error('arm base x is outside the workspace');
  }

  if (screenBaseY <= margin || screenBaseY >= level.workspace.height - margin) {
    throw new Error('arm base y is outside the workspace');
  }

  if (screenTargetX <= margin || screenTargetX >= level.workspace.width - margin) {
    throw new Error('target x is outside the workspace');
  }

  if (screenTargetY <= margin || screenTargetY >= level.workspace.height - margin) {
    throw new Error('target y is outside the workspace');
  }

  if (distanceFromBase <= 60) {
    throw new Error('target is too close to the arm base');
  }

  if (level.arm.solutionAngles.every((angle) => angle === 0)) {
    throw new Error('solution angles cannot all be zero');
  }

  if (Array.isArray(level.obstacles)) {
    for (const obstacle of level.obstacles) {
      for (const part of obstacle.parts || []) {
        const screenLeft = level.workspace.origin.x + part.x;
        const screenRight = screenLeft + part.width;
        const screenTop = level.workspace.origin.y - (part.y + part.height);
        const screenBottom = screenTop + part.height;

        if (screenLeft <= margin || screenRight >= level.workspace.width - margin) {
          throw new Error('obstacle x is outside the workspace');
        }

        if (screenTop <= margin || screenBottom >= level.workspace.height - margin) {
          throw new Error('obstacle y is outside the workspace');
        }
      }
    }
  }

  return level;
}

