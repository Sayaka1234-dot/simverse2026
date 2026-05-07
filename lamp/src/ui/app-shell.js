export function createAppShell(root) {
  root.innerHTML = `
    <div class="app-shell">
      <section class="canvas-stage">
        <canvas id="game-canvas" width="800" height="600"></canvas>
      </section>
      <aside class="sidebar" data-role="control-sidebar">
        <header class="sidebar-block">
          <h1>Mechanical Lamp Puzzle</h1>
          <p>Enter absolute angles to cover the target.</p>
        </header>
        <section class="sidebar-block" data-role="angle-controls"></section>
        <section class="sidebar-block">
          <ul class="debug-list">
            <li data-key="target">Target: --</li>
            <li data-key="bulb">Bulb: --</li>
            <li data-key="distance">Distance: --</li>
            <li data-key="radius">Light Radius: --</li>
            <li data-key="blocked">Blocked: --</li>
            <li data-key="covered">Covered: --</li>
          </ul>
        </section>
        <section class="sidebar-block" data-role="level-panel"></section>
      </aside>
    </div>
  `;

  return {
    canvas: root.querySelector('#game-canvas'),
    sidebar: root.querySelector('[data-role="control-sidebar"]'),
    controlsHost: root.querySelector('[data-role="angle-controls"]'),
    debugList: root.querySelector('.debug-list'),
    levelPanel: root.querySelector('[data-role="level-panel"]')
  };
}
