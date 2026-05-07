import { toScreenPoint } from '../core/kinematics.js';

export function drawLamp(ctx, workspace, bulb, lightRadius, solved) {
  const point = toScreenPoint({
    workspaceOrigin: workspace.origin,
    point: bulb
  });

  ctx.save();
  ctx.fillStyle = solved ? 'rgba(110, 231, 183, 0.24)' : 'rgba(253, 224, 71, 0.18)';
  ctx.beginPath();
  ctx.arc(point.x, point.y, lightRadius, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = solved ? '#86efac' : '#fde68a';
  ctx.beginPath();
  ctx.arc(point.x, point.y, 8, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}
