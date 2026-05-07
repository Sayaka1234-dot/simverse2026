export function createGameState({ manifest }) {
  let currentLevelIndex = 0;
  let currentLevel = null;
  let currentAngles = [];
  let solved = false;

  return {
    setLevel(level, index) {
      currentLevel = level;
      currentLevelIndex = index;
      currentAngles = [...level.arm.initialAngles];
      solved = false;
    },
    setAngle(index, angle) {
      currentAngles[index] = angle;
    },
    resetAngles() {
      currentAngles = [...currentLevel.arm.initialAngles];
    },
    markSolved(value) {
      solved = value;
    },
    advanceLevel() {
      if (solved && currentLevelIndex < manifest.length - 1) {
        currentLevelIndex += 1;
      }
    },
    snapshot() {
      return {
        currentLevelIndex,
        currentLevel,
        currentAngles: [...currentAngles],
        solved
      };
    }
  };
}
