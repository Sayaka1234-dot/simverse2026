function snapAngle(rawValue, step, min, max) {
  const clamped = Math.min(max, Math.max(min, Number(rawValue)));

  return Math.round(clamped / step) * step;
}

export function renderAngleControls({ host, level, angles, onAngleChange }) {
  const rows = level.arm.segments
    .map((segment, index) => {
      const value = angles[index];

      return `
        <label class="angle-row" data-index="${index}">
          <span>Joint ${index + 1} (${segment.length})</span>
          <input type="number" value="${value}" min="${level.arm.angleMin}" max="${level.arm.angleMax}" step="${level.arm.angleStep}" />
          <input type="range" value="${value}" min="${level.arm.angleMin}" max="${level.arm.angleMax}" step="${level.arm.angleStep}" />
          <output>${value}°</output>
        </label>
      `;
    })
    .join('');

  host.innerHTML = `<div class="angle-grid">${rows}</div>`;

  host.querySelectorAll('.angle-row').forEach((row) => {
    const index = Number(row.dataset.index);
    const numberInput = row.querySelector('input[type="number"]');
    const rangeInput = row.querySelector('input[type="range"]');
    const output = row.querySelector('output');

    const sync = (rawValue) => {
      const snapped = snapAngle(rawValue, level.arm.angleStep, level.arm.angleMin, level.arm.angleMax);
      numberInput.value = String(snapped);
      rangeInput.value = String(snapped);
      output.textContent = `${snapped}°`;
      onAngleChange(index, snapped);
    };

    numberInput.addEventListener('change', () => sync(numberInput.value));
    rangeInput.addEventListener('input', () => sync(rangeInput.value));
  });
}
