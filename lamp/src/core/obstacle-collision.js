function pointInRect(point, rect) {
  return (
    point.x >= rect.x &&
    point.x <= rect.x + rect.width &&
    point.y >= rect.y &&
    point.y <= rect.y + rect.height
  );
}

function orientation(a, b, c) {
  const value = (b.y - a.y) * (c.x - b.x) - ((b.x - a.x) * (c.y - b.y));

  if (Math.abs(value) < 1e-9) {
    return 0;
  }

  return value > 0 ? 1 : 2;
}

function onSegment(a, b, c) {
  return (
    Math.min(a.x, c.x) - 1e-9 <= b.x &&
    b.x <= Math.max(a.x, c.x) + 1e-9 &&
    Math.min(a.y, c.y) - 1e-9 <= b.y &&
    b.y <= Math.max(a.y, c.y) + 1e-9
  );
}

function segmentsIntersect(a1, a2, b1, b2) {
  const o1 = orientation(a1, a2, b1);
  const o2 = orientation(a1, a2, b2);
  const o3 = orientation(b1, b2, a1);
  const o4 = orientation(b1, b2, a2);

  if (o1 !== o2 && o3 !== o4) {
    return true;
  }

  if (o1 === 0 && onSegment(a1, b1, a2)) {
    return true;
  }
  if (o2 === 0 && onSegment(a1, b2, a2)) {
    return true;
  }
  if (o3 === 0 && onSegment(b1, a1, b2)) {
    return true;
  }
  if (o4 === 0 && onSegment(b1, a2, b2)) {
    return true;
  }

  return false;
}

function segmentIntersectsRect(start, end, rect) {
  if (pointInRect(start, rect) || pointInRect(end, rect)) {
    return true;
  }

  const topLeft = { x: rect.x, y: rect.y + rect.height };
  const topRight = { x: rect.x + rect.width, y: rect.y + rect.height };
  const bottomLeft = { x: rect.x, y: rect.y };
  const bottomRight = { x: rect.x + rect.width, y: rect.y };

  return (
    segmentsIntersect(start, end, topLeft, topRight) ||
    segmentsIntersect(start, end, topRight, bottomRight) ||
    segmentsIntersect(start, end, bottomRight, bottomLeft) ||
    segmentsIntersect(start, end, bottomLeft, topLeft)
  );
}

export function expandObstacleRects(obstacles = []) {
  return obstacles.flatMap((obstacle) =>
    (obstacle.parts || []).map((part) => ({
      obstacleId: obstacle.id,
      ...part
    }))
  );
}

export function computeObstacleCollision({ joints, obstacles = [] }) {
  const obstacleIds = new Set();
  const rects = expandObstacleRects(obstacles);

  for (let index = 0; index < joints.length - 1; index += 1) {
    const start = joints[index];
    const end = joints[index + 1];

    for (const rect of rects) {
      if (segmentIntersectsRect(start, end, rect)) {
        obstacleIds.add(rect.obstacleId);
      }
    }
  }

  return {
    blocked: obstacleIds.size > 0,
    obstacleIds: [...obstacleIds]
  };
}
