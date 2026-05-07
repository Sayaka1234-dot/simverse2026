import { toScreenPoint } from '../core/kinematics.js';
import { drawBlueprintGrid } from './blueprint-grid.js';
import { drawLamp } from './lamp-renderer.js';

function getSegmentLabel(level, chain, index) {
  const configuredLength = level.arm?.segments?.[index]?.length;

  if (Number.isFinite(configuredLength)) {
    return String(Math.round(configuredLength));
  }

  const start = chain.joints[index];
  const end = chain.joints[index + 1];
  const length = Math.hypot(end.x - start.x, end.y - start.y);

  return String(Math.round(length));
}

function drawBaseMarker(ctx, point) {
  const size = 8;

  ctx.save();
  ctx.strokeStyle = '#fb923c';
  ctx.fillStyle = '#7c2d12';
  ctx.lineWidth = 2.5;

  ctx.beginPath();
  ctx.moveTo(point.x, point.y - size);
  ctx.lineTo(point.x + size, point.y);
  ctx.lineTo(point.x, point.y + size);
  ctx.lineTo(point.x - size, point.y);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = '#fdba74';
  ctx.beginPath();
  ctx.arc(point.x, point.y, 2.5, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

function drawJointMarkers(ctx, level, joints) {
  ctx.save();

  joints.forEach((joint, index) => {
    const point = toScreenPoint({
      workspaceOrigin: level.workspace.origin,
      point: joint
    });

    if (index === 0) {
      drawBaseMarker(ctx, point);
      return;
    }

    ctx.strokeStyle = '#7dd3fc';
    ctx.fillStyle = '#082f49';
    ctx.lineWidth = 2;

    ctx.beginPath();
    ctx.arc(point.x, point.y, 6, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = '#e0f2fe';
    ctx.beginPath();
    ctx.arc(point.x, point.y, 2, 0, Math.PI * 2);
    ctx.fill();
  });

  ctx.restore();
}

function drawSegmentLength(ctx, start, end, label) {
  const deltaX = end.x - start.x;
  const deltaY = end.y - start.y;
  const magnitude = Math.hypot(deltaX, deltaY) || 1;
  const normalX = -deltaY / magnitude;
  const normalY = deltaX / magnitude;
  const midX = (start.x + end.x) / 2;
  const midY = (start.y + end.y) / 2;
  const tickHalf = 8;
  const leaderLength = 12;
  const labelOffset = 26;

  ctx.save();
  ctx.strokeStyle = 'rgba(125, 211, 252, 0.5)';
  ctx.fillStyle = '#bae6fd';
  ctx.lineWidth = 1.5;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.font = '12px "JetBrains Mono", monospace';

  ctx.beginPath();
  ctx.moveTo(midX - normalX * tickHalf, midY - normalY * tickHalf);
  ctx.lineTo(midX + normalX * tickHalf, midY + normalY * tickHalf);
  ctx.stroke();

  ctx.beginPath();
  ctx.moveTo(midX + normalX * tickHalf, midY + normalY * tickHalf);
  ctx.lineTo(midX + normalX * leaderLength, midY + normalY * leaderLength);
  ctx.stroke();

  ctx.fillText(label, midX + normalX * labelOffset, midY + normalY * labelOffset);
  ctx.restore();
}

function drawObstaclePart(ctx, workspaceOrigin, part) {
  const screenX = workspaceOrigin.x + part.x;
  const screenY = workspaceOrigin.y - (part.y + part.height);
  const stripeSpacing = 10;

  ctx.save();
  ctx.fillStyle = 'rgba(245, 158, 11, 0.18)';
  ctx.strokeStyle = '#f59e0b';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.rect(screenX, screenY, part.width, part.height);
  ctx.fill();
  ctx.stroke();

  ctx.beginPath();
  ctx.rect(screenX, screenY, part.width, part.height);
  ctx.clip();
  ctx.strokeStyle = 'rgba(251, 191, 36, 0.9)';
  ctx.lineWidth = 2;

  for (let offset = -part.height; offset <= part.width + part.height; offset += stripeSpacing) {
    ctx.beginPath();
    ctx.moveTo(screenX + offset, screenY + part.height);
    ctx.lineTo(screenX + offset + part.height, screenY);
    ctx.stroke();
  }

  ctx.restore();
}

function drawObstacles(ctx, level) {
  for (const obstacle of level.obstacles || []) {
    for (const part of obstacle.parts || []) {
      drawObstaclePart(ctx, level.workspace.origin, part);
    }
  }
}

export function renderFrame(ctx, { level, chain, coverage }) {
  ctx.clearRect(0, 0, level.workspace.width, level.workspace.height);
  drawBlueprintGrid(ctx, level.workspace);
  drawObstacles(ctx, level);

  ctx.save();
  ctx.strokeStyle = '#e2e8f0';
  ctx.lineWidth = 4;

  for (let index = 0; index < chain.joints.length - 1; index += 1) {
    const start = toScreenPoint({
      workspaceOrigin: level.workspace.origin,
      point: chain.joints[index]
    });
    const end = toScreenPoint({
      workspaceOrigin: level.workspace.origin,
      point: chain.joints[index + 1]
    });

    ctx.beginPath();
    ctx.moveTo(start.x, start.y);
    ctx.lineTo(end.x, end.y);
    ctx.stroke();

    drawSegmentLength(ctx, start, end, getSegmentLabel(level, chain, index));
  }

  drawJointMarkers(ctx, level, chain.joints);

  const target = toScreenPoint({
    workspaceOrigin: level.workspace.origin,
    point: level.target
  });

  ctx.fillStyle = coverage.covered ? '#22d3ee' : '#f97316';
  ctx.beginPath();
  ctx.arc(target.x, target.y, 7, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();

  drawLamp(ctx, level.workspace, chain.bulb, level.lamp.lightRadius, coverage.solved);
}
