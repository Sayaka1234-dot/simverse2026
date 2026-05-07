import fs from "node:fs/promises";
import { readFileSync } from "node:fs";
import path from "node:path";
import ResourceMgr, { initializeResources } from "@/resources/ResourceMgr";
import RES_DATA from "@/resources/ResData";
import ResourceType from "@/resources/ResourceType";
import JsonLoader from "@/resources/JsonLoader";
import LevelState from "@/game/LevelState";
import GameScene from "@/GameScene";
import textCommandController from "@/game/TextCommandController";
import SoundMgr from "@/game/CTRSoundMgr";
import type { LevelJson, RawBoxMetadataJson } from "@/types/json";

export interface HeadlessEvalCase {
    level: string;
    commands: string | string[];
    maxSeconds?: number;
    stepSeconds?: number;
}

export interface HeadlessEvalResult {
    level: string;
    won: boolean;
    stars: number;
    time: number;
    score: number;
    reason: "won" | "lost" | "timeout";
    frames: number;
}

const DEFAULT_MAX_SECONDS = 30;
const DEFAULT_STEP_SECONDS = 1 / 60;
const DUMMY_CANVAS_SIZE = 4096;

let resourcesPrimed = false;

const primeJsonLoader = (): void => {
    const loader = JsonLoader as unknown as {
        jsonCache?: Map<string, unknown>;
    };

    if (!loader.jsonCache || loader.jsonCache.has("boxMetadata")) {
        return;
    }

    const metadataPath = path.join(
        process.cwd(),
        "public",
        "data",
        "config",
        "editions",
        "net-box-text.json"
    );
    const metadata = JSON.parse(readFileSync(metadataPath, "utf8")) as RawBoxMetadataJson[];
    loader.jsonCache.set("boxMetadata", metadata);
};

const ensureResources = (): void => {
    if (resourcesPrimed) {
        return;
    }

    primeJsonLoader();
    initializeResources();

    const canvas = document.createElement("canvas") as HTMLCanvasElement;
    canvas.width = DUMMY_CANVAS_SIZE;
    canvas.height = DUMMY_CANVAS_SIZE;

    for (let i = 0; i < RES_DATA.length; i++) {
        const entry = RES_DATA[i];
        if (!entry) {
            continue;
        }
        if (entry.type === ResourceType.IMAGE || entry.type === ResourceType.FONT) {
            entry._atlasFailed = true;
            ResourceMgr.onResourceLoaded(i, {
                drawable: canvas,
                width: canvas.width,
                height: canvas.height,
                sourceUrl: "headless://dummy",
            });
        }
    }

    SoundMgr.setSoundEnabled(false);
    SoundMgr.setMusicEnabled(false);

    resourcesPrimed = true;
};

const normalizeLevelFile = (level: string): string => {
    const trimmed = level.trim();
    if (!trimmed) {
        throw new Error("level is required");
    }
    return trimmed.endsWith(".json") ? trimmed : `${trimmed}.json`;
};

const resolveLevelPath = (level: string): string => {
    if (path.isAbsolute(level)) {
        return level;
    }
    return path.join(process.cwd(), "public", "data", "boxes", "levels", level);
};

const parsePackLevel = (levelPath: string): { packIndex: number; levelIndex: number } | null => {
    const base = path.basename(levelPath);
    const match = base.match(/(\d{2})-(\d+)/);
    if (!match) {
        return null;
    }
    return {
        packIndex: Math.max(0, parseInt(match[1]!, 10) - 1),
        levelIndex: Math.max(0, parseInt(match[2]!, 10) - 1),
    };
};

const loadLevelJson = async (levelPath: string): Promise<LevelJson> => {
    const raw = await fs.readFile(levelPath, "utf8");
    return JSON.parse(raw) as LevelJson;
};

const normalizeCommands = (commands: string | string[]): string => {
    if (Array.isArray(commands)) {
        return commands.join("\n");
    }
    return commands;
};

export const evaluateLevelHeadless = async (
    input: HeadlessEvalCase
): Promise<HeadlessEvalResult> => {
    ensureResources();

    const levelFile = normalizeLevelFile(input.level);
    const levelPath = resolveLevelPath(levelFile);
    const levelJson = await loadLevelJson(levelPath);

    LevelState.loadedMap = levelJson;
    const parsed = parsePackLevel(levelPath);
    if (parsed) {
        LevelState.pack = parsed.packIndex;
        LevelState.level = parsed.levelIndex;
    } else {
        LevelState.pack = 0;
        LevelState.level = 0;
    }

    let won = false;
    let lost = false;

    const scene = new GameScene();
    scene.gameController = {
        avgDelta: input.stepSeconds ?? DEFAULT_STEP_SECONDS,
        frameBalance: 0,
        onLevelWon: () => {
            won = true;
        },
        onLevelLost: () => {
            lost = true;
        },
    };

    scene.show();

    const commandText = normalizeCommands(input.commands);
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

    const stepSeconds = input.stepSeconds ?? DEFAULT_STEP_SECONDS;
    const maxSeconds = input.maxSeconds ?? DEFAULT_MAX_SECONDS;
    const maxFrames = Math.max(1, Math.ceil(maxSeconds / stepSeconds));
    let frames = 0;

    while (frames < maxFrames && !won && !lost) {
        scene.update(stepSeconds);
        frames += 1;
    }

    textCommandController.stop();

    const reason: HeadlessEvalResult["reason"] = won ? "won" : lost ? "lost" : "timeout";

    return {
        level: levelFile,
        won,
        stars: scene.starsCollected,
        time: scene.time,
        score: scene.score,
        reason,
        frames,
    };
};
