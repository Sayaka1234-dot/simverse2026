function buildSegmentDescriptors(segments) {
  return segments.map((segment, index) => ({
    joint: index + 1,
    length: segment.length
  }));
}

function buildObstacleDescriptors(obstacles = []) {
  return obstacles.map((obstacle) => ({
    id: obstacle.id,
    type: obstacle.type,
    pattern: obstacle.pattern,
    parts: obstacle.parts.map((part) => ({ ...part }))
  }));
}

export function buildTaskPayload({
  level,
  imageDirName = 'images',
  levelDirName = 'levels',
  taskType = 'mechanical_lamp_targeting'
}) {
  const armBaseOffset = level.armBaseOffset || { x: 0, y: 0 };
  const obstacleDescriptors = buildObstacleDescriptors(level.obstacles || []);

  return {
    sample_id: level.id,
    task_type: taskType,
    public: {
      image: `${imageDirName}/${level.id}.png`,
      target: { ...level.target },
      arm_base: { ...armBaseOffset },
      segment_count: level.arm.segmentCount,
      segments: buildSegmentDescriptors(level.arm.segments),
      lamp: {
        light_radius: level.lamp.lightRadius
      },
      angle_constraints: {
        step: level.arm.angleStep,
        min: level.arm.angleMin,
        max: level.arm.angleMax
      },
      coordinate_system: {
        origin_is_coordinate_origin: true,
        arm_base_may_differ_from_origin: true,
        angles_are_absolute_from_positive_x_axis: true
      },
      obstacles: obstacleDescriptors
    },
    validator: {
      source_level: `${levelDirName}/${level.id}.json`,
      solution_angles: [...level.arm.solutionAngles],
      target: { ...level.target },
      arm_base: { ...armBaseOffset },
      success_rule: {
        type: 'distance_within_radius',
        radius: level.lamp.lightRadius
      },
      obstacles: obstacleDescriptors
    },
    metadata: {
      difficulty: level.difficulty
    }
  };
}

export function buildManifestRows({ tasks, taskDirName = 'task' }) {
  return tasks.map((task) => ({
    sample_id: task.sample_id,
    task_path: `${taskDirName}/${task.sample_id}.json`,
    image: task.public.image
  }));
}

export function serializeManifestRows(rows) {
  return `${rows.map((row) => JSON.stringify(row)).join('\n')}\n`;
}
