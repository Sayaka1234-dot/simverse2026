import { toScreenPoint } from '../core/kinematics.js';

function formatAxisValue(value) {
  const rounded = Math.round(value);

  if (Math.abs(rounded) < 1) {
    return '0';
  }

  return String(rounded);
}

function drawAxisLabels(ctx, workspace, screenOrigin) {
  const xLabelY = screenOrigin.y > workspace.height - 24
    ? screenOrigin.y - 14
    : screenOrigin.y + 16;
  const yLabelX = screenOrigin.x < 28
    ? screenOrigin.x + 16
    : screenOrigin.x - 16;

  ctx.save();
  ctx.fillStyle = 'rgba(224, 242, 254, 0.9)';
  ctx.font = '11px "JetBrains Mono", monospace';
  ctx.textBaseline = 'middle';

  for (let x = 0; x <= workspace.width; x += workspace.gridSize) {
    const worldX = x - screenOrigin.x;
    ctx.textAlign = 'center';
    ctx.fillText(formatAxisValue(worldX), x, xLabelY);
  }

  for (let y = 0; y <= workspace.height; y += workspace.gridSize) {
    const worldY = screenOrigin.y - y;
    ctx.textAlign = yLabelX < screenOrigin.x ? 'right' : 'left';
    ctx.fillText(formatAxisValue(worldY), yLabelX, y);
  }

  ctx.restore();
}

export function drawBlueprintGrid(ctx, workspace) {
  ctx.save();
  ctx.fillStyle = '#06233a';
  ctx.fillRect(0, 0, workspace.width, workspace.height);
  ctx.strokeStyle = 'rgba(125, 211, 252, 0.12)';

  for (let x = 0; x <= workspace.width; x += workspace.gridSize) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, workspace.height);
    ctx.stroke();
  }

  for (let y = 0; y <= workspace.height; y += workspace.gridSize) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(workspace.width, y);
    ctx.stroke();
  }

  const screenOrigin = toScreenPoint({
    workspaceOrigin: workspace.origin,
    point: { x: 0, y: 0 }
  });

  ctx.save();
  ctx.strokeStyle = 'rgba(125, 211, 252, 0.35)';
  ctx.lineWidth = 2;

  ctx.beginPath();
  ctx.moveTo(screenOrigin.x, 0);
  ctx.lineTo(screenOrigin.x, workspace.height);
  ctx.stroke();

  ctx.beginPath();
  ctx.moveTo(0, screenOrigin.y);
  ctx.lineTo(workspace.width, screenOrigin.y);
  ctx.stroke();
  ctx.restore();

  drawAxisLabels(ctx, workspace, screenOrigin);

  ctx.fillStyle = '#f8fafc';
  ctx.beginPath();
  ctx.arc(screenOrigin.x, screenOrigin.y, 5, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}
