const GRID_UNIT = 40;
const WORLD_MARGIN = 40;

const OBSTACLE_TEMPLATES = [
  {
    type: 'block',
    parts: [{ x: 0, y: 0, width: 80, height: 80 }]
  },
  {
    type: 'bar_horizontal',
    parts: [{ x: 0, y: 0, width: 120, height: 40 }]
  },
  {
    type: 'bar_vertical',
    parts: [{ x: 0, y: 0, width: 40, height: 120 }]
  },
  {
    type: 'l_corner',
    parts: [
      { x: 0, y: 0, width: 80, height: 40 },
      { x: 0, y: 0, width: 40, height: 120 }
    ]
  },
  {
    type: 'stair',
    parts: [
      { x: 0, y: 0, width: 80, height: 40 },
      { x: 40, y: 40, width: 80, height: 40 }
    ]
  }
];

function roundPoint(point) {
  return {
    x: Number(point.x.toFixed(2)),
    y: Number(point.y.toFixed(2))
  };
}

function computeChain({ origin, segments, angles }) {
  const joints = [roundPoint(origin)];
  let x = origin.x;
  let y = origin.y;

  segments.forEach((segment, index) => {
    const radians = (angles[index] * Math.PI) / 180;
    x += segment.length * Math.cos(radians);
    y += segment.length * Math.sin(radians);
    joints.push(roundPoint({ x, y }));
  });

  return joints;
}

function pointInRect(point, rect) {
  return (
    point.x >= rect.x &&
    point.x <= rect.x + rect.width &&
    point.y >= rect.y &&
    point.y <= rect.y + rect.height
  );
}

function orientation(a, b, c) {
  const value = (b.y - a.y) * (c.x - b.x) - (b.x - a.x) * (c.y - b.y);
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

function rectsOverlap(a, b) {
  return !(
    a.x + a.width <= b.x ||
    b.x + b.width <= a.x ||
    a.y + a.height <= b.y ||
    b.y + b.height <= a.y
  );
}

function expandObstacleRects(obstacles) {
  return obstacles.flatMap((obstacle) => obstacle.parts);
}

function obstacleIntersectsChain(obstacle, joints) {
  for (let index = 0; index < joints.length - 1; index += 1) {
    const start = joints[index];
    const end = joints[index + 1];

    if (obstacle.parts.some((part) => segmentIntersectsRect(start, end, part))) {
      return true;
    }
  }

  return false;
}

function obstacleIntersectsSegment(obstacle, start, end) {
  return obstacle.parts.some((part) => segmentIntersectsRect(start, end, part));
}

function obstacleContainsPoint(obstacle, point) {
  return obstacle.parts.some((part) => pointInRect(point, part));
}

function obstacleInBounds(obstacle, workspace) {
  return obstacle.parts.every((part) => {
    const screenLeft = workspace.origin.x + part.x;
    const screenRight = screenLeft + part.width;
    const screenTop = workspace.origin.y - (part.y + part.height);
    const screenBottom = screenTop + part.height;

    return (
      screenLeft > WORLD_MARGIN &&
      screenRight < workspace.width - WORLD_MARGIN &&
      screenTop > WORLD_MARGIN &&
      screenBottom < workspace.height - WORLD_MARGIN
    );
  });
}

function obstacleOverlapsAny(obstacle, others) {
  return expandObstacleRects(others).some((otherRect) =>
    obstacle.parts.some((part) => rectsOverlap(part, otherRect))
  );
}

function pointToSegmentDistance(point, start, end) {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const lengthSquared = (dx * dx) + (dy * dy);

  if (lengthSquared === 0) {
    return Math.hypot(point.x - start.x, point.y - start.y);
  }

  const t = Math.max(0, Math.min(1, (((point.x - start.x) * dx) + ((point.y - start.y) * dy)) / lengthSquared));
  const projection = {
    x: start.x + (t * dx),
    y: start.y + (t * dy)
  };

  return Math.hypot(point.x - projection.x, point.y - projection.y);
}

function obstacleNearSegment(obstacle, start, end, maxDistance = GRID_UNIT * 1.5) {
  return obstacle.parts.some((part) => {
    const center = {
      x: part.x + (part.width / 2),
      y: part.y + (part.height / 2)
    };

    return pointToSegmentDistance(center, start, end) <= maxDistance;
  });
}

function buildCorridorRect(start, end, padding = GRID_UNIT * 1.5) {
  return {
    x: Math.min(start.x, end.x) - padding,
    y: Math.min(start.y, end.y) - padding,
    width: Math.abs(end.x - start.x) + (padding * 2),
    height: Math.abs(end.y - start.y) + (padding * 2)
  };
}

function obstacleTouchesCorridor(obstacle, start, end, padding = GRID_UNIT * 1.5) {
  const corridor = buildCorridorRect(start, end, padding);
  return obstacle.parts.some((part) => rectsOverlap(part, corridor));
}

function createObstacle(template, anchor, index) {
  return {
    id: `wall_${index + 1}`,
    type: template.type,
    pattern: 'warning_stripes',
    parts: template.parts.map((part) => ({
      x: anchor.x + part.x,
      y: anchor.y + part.y,
      width: part.width,
      height: part.height
    }))
  };
}

function createGridAnchors(workspace) {
  const minWorldX = WORLD_MARGIN - workspace.origin.x;
  const maxWorldX = workspace.width - WORLD_MARGIN - workspace.origin.x - (GRID_UNIT * 3);
  const minWorldY = workspace.origin.y - (workspace.height - WORLD_MARGIN);
  const maxWorldY = workspace.origin.y - WORLD_MARGIN - (GRID_UNIT * 3);

  const anchors = [];

  for (let x = Math.ceil(minWorldX / GRID_UNIT) * GRID_UNIT; x <= maxWorldX; x += GRID_UNIT) {
    for (let y = Math.ceil(minWorldY / GRID_UNIT) * GRID_UNIT; y <= maxWorldY; y += GRID_UNIT) {
      anchors.push({ x, y });
    }
  }

  return anchors;
}

function sortCandidatesByPriority(candidates, base, target) {
  const midpoint = {
    x: (base.x + target.x) / 2,
    y: (base.y + target.y) / 2
  };

  return [...candidates].sort((left, right) => {
    const leftCenter = {
      x: left.parts[0].x + (left.parts[0].width / 2),
      y: left.parts[0].y + (left.parts[0].height / 2)
    };
    const rightCenter = {
      x: right.parts[0].x + (right.parts[0].width / 2),
      y: right.parts[0].y + (right.parts[0].height / 2)
    };

    return (
      Math.hypot(leftCenter.x - midpoint.x, leftCenter.y - midpoint.y) -
      Math.hypot(rightCenter.x - midpoint.x, rightCenter.y - midpoint.y)
    );
  });
}

export function buildObstacleVariantLevel({ level, random = Math.random }) {
  const base = level.armBaseOffset || { x: 0, y: 0 };
  const solutionJoints = computeChain({
    origin: base,
    segments: level.arm.segments,
    angles: level.arm.solutionAngles
  });
  const initialJoints = computeChain({
    origin: base,
    segments: level.arm.segments,
    angles: level.arm.initialAngles
  });
  const directSegment = {
    start: base,
    end: level.target
  };

  const primaryCandidates = [];
  const corridorCandidates = [];
  const fallbackCandidates = [];

  for (const template of OBSTACLE_TEMPLATES) {
    for (const anchor of createGridAnchors(level.workspace)) {
      const obstacle = createObstacle(template, anchor, fallbackCandidates.length);
      if (!obstacleInBounds(obstacle, level.workspace)) {
        continue;
      }
      if (obstacleContainsPoint(obstacle, base) || obstacleContainsPoint(obstacle, level.target)) {
        continue;
      }
      if (obstacleIntersectsChain(obstacle, solutionJoints) || obstacleIntersectsChain(obstacle, initialJoints)) {
        continue;
      }

      fallbackCandidates.push(obstacle);

      if (obstacleIntersectsSegment(obstacle, directSegment.start, directSegment.end)) {
        primaryCandidates.push(obstacle);
        continue;
      }

      if (obstacleNearSegment(obstacle, directSegment.start, directSegment.end)) {
        corridorCandidates.push(obstacle);
        continue;
      }

      if (obstacleTouchesCorridor(obstacle, directSegment.start, directSegment.end)) {
        corridorCandidates.push(obstacle);
      }
    }
  }

  const selected = [];
  const distinctTypes = new Set();
  const candidatePool = (
    primaryCandidates.length > 0
      ? primaryCandidates
      : (corridorCandidates.length > 0 ? corridorCandidates : fallbackCandidates)
  );
  const prioritized = sortCandidatesByPriority(candidatePool, base, level.target);

  while (prioritized.length > 0 && selected.length < 2) {
    const pickIndex = Math.floor(random() * Math.min(prioritized.length, 6));
    const obstacle = prioritized.splice(pickIndex, 1)[0];

    if (obstacleOverlapsAny(obstacle, selected)) {
      continue;
    }

    if (selected.length > 0 && distinctTypes.has(obstacle.type) && prioritized.some((item) => !distinctTypes.has(item.type))) {
      continue;
    }

    selected.push({
      ...obstacle,
      id: `wall_${selected.length + 1}`
    });
    distinctTypes.add(obstacle.type);
  }

  if (selected.length === 0) {
    throw new Error(`Unable to place obstacle walls for ${level.id}`);
  }

  return {
    ...level,
    obstacles: selected,
    meta: {
      ...(level.meta || {}),
      showDebugInfo: true,
      variant: 'walls'
    }
  };
}

export function obstacleBlocksChain({ joints, obstacles = [] }) {
  return obstacles.some((obstacle) => obstacleIntersectsChain(obstacle, joints));
}
