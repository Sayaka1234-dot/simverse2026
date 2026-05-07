const DEG_TO_RAD = Math.PI / 180;

export function solveTarget(lengths, solutionAngles) {
  let x = 0;
  let y = 0;

  lengths.forEach((length, index) => {
    const radians = solutionAngles[index] * DEG_TO_RAD;
    x += length * Math.cos(radians);
    y += length * Math.sin(radians);
  });

  return {
    x: Number(x.toFixed(2)),
    y: Number(y.toFixed(2))
  };
}
