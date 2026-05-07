import Canvas from "@/utils/Canvas";
import PreLoader from "@/resources/PreLoader";
import LevelState from "@/game/LevelState";
import GameScene from "@/GameScene";
import resolution from "@/resolution";
import type { LevelJson } from "@/types/json";

const VITE_ENV = (import.meta as ImportMeta & { env?: { BASE_URL?: string } }).env;

const normalizeLevelFile = (levelFile: string): string => {
    const trimmed = levelFile.trim();
    if (!trimmed) {
        throw new Error("levelFile is required");
    }
    return trimmed.endsWith(".json") ? trimmed : `${trimmed}.json`;
};

const parsePackLevelFromFile = (
    levelFile: string
): { packIndex: number; levelIndex: number } | null => {
    const match = levelFile.match(/(\d{2})-(\d+)/);
    if (!match) {
        return null;
    }
    const packIndex = Math.max(0, parseInt(match[1]!, 10) - 1);
    const levelIndex = Math.max(0, parseInt(match[2]!, 10) - 1);
    return { packIndex, levelIndex };
};

const fetchLevelJson = async (levelFile: string): Promise<LevelJson> => {
    const baseUrl = (VITE_ENV?.BASE_URL || "/").replace(/\/$/, "");
    const url = `${baseUrl}/data/boxes/levels/${levelFile}`;
    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(`Failed to load level JSON (${response.status}) for ${levelFile}`);
    }
    return (await response.json()) as LevelJson;
};

let readyPromise: Promise<void> | null = null;

const ensureCaptureReady = (): Promise<void> => {
    if (readyPromise) {
        return readyPromise;
    }

    readyPromise = new Promise((resolve) => {
        PreLoader.start();
        PreLoader.domReady();

        Canvas.domReady("captureCanvas");
        if (!Canvas.element) {
            throw new Error("captureCanvas element not found");
        }

        Canvas.element.width = resolution.CANVAS_WIDTH;
        Canvas.element.height = resolution.CANVAS_HEIGHT;
        Canvas.element.style.width = `${resolution.CANVAS_WIDTH}px`;
        Canvas.element.style.height = `${resolution.CANVAS_HEIGHT}px`;

        PreLoader.run(() => {
            resolve();
        });
    });

    return readyPromise;
};

const renderLevel = async (levelFile: string): Promise<string> => {
    const normalized = normalizeLevelFile(levelFile);
    await ensureCaptureReady();

    const levelJson = await fetchLevelJson(normalized);
    LevelState.loadedMap = levelJson;

    const parsed = parsePackLevelFromFile(normalized);
    if (parsed) {
        LevelState.pack = parsed.packIndex;
        LevelState.level = parsed.levelIndex;
    } else {
        LevelState.pack = 0;
        LevelState.level = 0;
    }

    const scene = new GameScene();
    scene.gameController = {
        avgDelta: 1 / 60,
        frameBalance: 0,
        onLevelWon: () => {},
        onLevelLost: () => {},
    };

    scene.show();
    scene.update(1 / 60);

    const ctx = Canvas.context;
    const canvas = Canvas.element;
    if (ctx && canvas) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
    scene.draw();

    if (!canvas) {
        throw new Error("captureCanvas not ready");
    }

    return canvas.toDataURL("image/png");
};

const params = new URLSearchParams(window.location.search);
const initialLevel = params.get("level");

declare global {
    interface Window {
        captureLevel?: (levelFile?: string) => Promise<string>;
    }
}

window.captureLevel = async (levelFile?: string) => {
    const target = levelFile || initialLevel;
    if (!target) {
        throw new Error("Missing level file");
    }
    return renderLevel(target);
};

if (initialLevel) {
    void renderLevel(initialLevel);
}
