import Canvas from "@/utils/Canvas";
import PreLoader from "@/resources/PreLoader";
import LevelState from "@/game/LevelState";
import GameScene from "@/GameScene";
import resolution from "@/resolution";
import textCommandController from "@/game/TextCommandController";
import type { LevelJson } from "@/types/json";

const VITE_ENV = (import.meta as ImportMeta & { env?: { BASE_URL?: string } }).env;

export interface EvalOptions {
    levelFile: string;
    commands: string | string[];
    maxSeconds?: number;
    stepSeconds?: number;
}

export interface EvalResult {
    won: boolean;
    stars: number;
    time: number;
    score: number;
    reason: "won" | "lost" | "timeout";
    frames: number;
    levelFile: string;
}

const DEFAULT_MAX_SECONDS = 30;
const DEFAULT_STEP_SECONDS = 1 / 60;

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

const normalizeCommands = (commands: string | string[]): string => {
    if (Array.isArray(commands)) {
        return commands.join("\n");
    }
    return commands;
};

let readyPromise: Promise<void> | null = null;

export const ensureEvalReady = (): Promise<void> => {
    if (readyPromise) {
        return readyPromise;
    }

    readyPromise = new Promise((resolve) => {
        let menuReady = false;
        let gameReady = false;
        const resolveWhenReady = () => {
            if (menuReady && gameReady) {
                resolve();
            }
        };

        PreLoader.start();
        PreLoader.domReady();

        const canvasId = document.getElementById("c") ? "c" : "evalCanvas";
        Canvas.domReady(canvasId);
        if (!Canvas.element) {
            throw new Error(`${canvasId} element not found`);
        }

        Canvas.element.width = resolution.CANVAS_WIDTH;
        Canvas.element.height = resolution.CANVAS_HEIGHT;
        Canvas.element.style.width = `${resolution.CANVAS_WIDTH}px`;
        Canvas.element.style.height = `${resolution.CANVAS_HEIGHT}px`;

        PreLoader.run(() => {
            menuReady = true;
            resolveWhenReady();
        });
        PreLoader.runWhenGameReady(() => {
            gameReady = true;
            resolveWhenReady();
        });
    });

    return readyPromise;
};

export const evaluateLevel = async (options: EvalOptions): Promise<EvalResult> => {
    const levelFile = normalizeLevelFile(options.levelFile);
    const maxSeconds = options.maxSeconds ?? DEFAULT_MAX_SECONDS;
    const stepSeconds = options.stepSeconds ?? DEFAULT_STEP_SECONDS;

    await ensureEvalReady();

    const levelJson = await fetchLevelJson(levelFile);
    LevelState.loadedMap = levelJson;

    const parsed = parsePackLevelFromFile(levelFile);
    if (parsed) {
        LevelState.pack = parsed.packIndex;
        LevelState.level = parsed.levelIndex;
    } else {
        LevelState.pack = 0;
        LevelState.level = 0;
    }

    const scene = new GameScene();
    let won = false;
    let lost = false;

    scene.gameController = {
        avgDelta: stepSeconds,
        frameBalance: 0,
        onLevelWon: () => {
            won = true;
        },
        onLevelLost: () => {
            lost = true;
        },
    };

    scene.show();

    const commandText = normalizeCommands(options.commands);
    textCommandController.load(commandText);
    textCommandController.start();
    if (textCommandController.status === "error") {
        const errors = textCommandController.commandList
            .filter((cmd) => cmd.status === "error")
            .map((cmd) => cmd.errorMsg)
            .filter((msg): msg is string => Boolean(msg));
        textCommandController.stop();
        throw new Error(errors.length > 0 ? errors.join("; ") : "Command parse error");
    }

    const maxFrames = Math.max(1, Math.ceil(maxSeconds / stepSeconds));
    let frames = 0;

    try {
        while (frames < maxFrames && !won && !lost) {
            scene.update(stepSeconds);
            frames += 1;
        }
    } finally {
        textCommandController.stop();
    }

    const reason: EvalResult["reason"] = won ? "won" : lost ? "lost" : "timeout";

    return {
        won,
        stars: scene.starsCollected,
        time: scene.time,
        score: scene.score,
        reason,
        frames,
        levelFile,
    };
};
