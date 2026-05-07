const DEG_TO_RAD = Math.PI / 180;

function roundPoint(point) {
  return {
    x: Number(point.x.toFixed(2)),
    y: Number(point.y.toFixed(2))
  };
}

export function computeArmChain({ origin, segments, angles }) {
  const joints = [roundPoint(origin)];
  let x = origin.x;
  let y = origin.y;

  segments.forEach((segment, index) => {
    const radians = angles[index] * DEG_TO_RAD;

    x += segment.length * Math.cos(radians);
    y += segment.length * Math.sin(radians);
    joints.push(roundPoint({ x, y }));
  });

  return {
    joints,
    bulb: joints[joints.length - 1]
  };
}

export function toScreenPoint({ workspaceOrigin, point }) {
  return {
    x: workspaceOrigin.x + point.x,
    y: workspaceOrigin.y - point.y
  };
}
