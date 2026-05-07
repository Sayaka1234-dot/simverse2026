export function computeCoverage({ target, bulb, lightRadius, blocked = false }) {
  const dx = target.x - bulb.x;
  const dy = target.y - bulb.y;
  const distance = Number(Math.hypot(dx, dy).toFixed(2));
  const covered = distance < lightRadius;

  return {
    distance,
    covered,
    blocked,
    solved: covered && !blocked
  };
}
