import './styles.css';
import { createAppShell } from './ui/app-shell.js';
import { loadManifest, loadLevel } from './core/level-loader.js';
import { renderFrame } from './render/canvas-renderer.js';
import { createGameController } from './core/game-controller.js';

const shell = createAppShell(document.querySelector('#app'));

createGameController({
  shell,
  services: {
    loadManifest,
    loadLevel,
    renderFrame
  }
}).start();
