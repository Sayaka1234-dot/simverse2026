export function renderLevelPanel({ host, levelIndex, levelCount, onReset, onNext, solved }) {
  host.innerHTML = `
    <div class="level-panel">
      <p>Level ${levelIndex + 1} / ${levelCount}</p>
      <button type="button" data-action="reset">Reset Angles</button>
      <button type="button" data-action="next" ${solved ? '' : 'disabled'}>Next Level</button>
    </div>
  `;

  host.querySelector('[data-action="reset"]').addEventListener('click', onReset);
  host.querySelector('[data-action="next"]').addEventListener('click', onNext);
}
