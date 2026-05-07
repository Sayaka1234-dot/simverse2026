export function updateHud(debugList, data) {
  debugList.querySelector('[data-key="target"]').textContent = `Target: (${data.target.x}, ${data.target.y})`;
  debugList.querySelector('[data-key="bulb"]').textContent = `Bulb: (${data.bulb.x}, ${data.bulb.y})`;
  debugList.querySelector('[data-key="distance"]').textContent = `Distance: ${data.distance}`;
  debugList.querySelector('[data-key="radius"]').textContent = `Light Radius: ${data.lightRadius}`;
  debugList.querySelector('[data-key="blocked"]').textContent = `Blocked: ${data.blocked ? 'Yes' : 'No'}`;
  debugList.querySelector('[data-key="covered"]').textContent = `Covered: ${data.covered ? (data.blocked ? 'Yes / Blocked' : 'Yes / Solved') : 'No'}`;
}
