import Canvas from "@/utils/Canvas";
import PreLoader from "@/resources/PreLoader";
import LevelState from "@/game/LevelState";
import GameScene from "@/GameScene";
import resolution from "@/resolution";
import type { LevelJson } from "@/types/json";

const VITE_ENV = (import.meta as ImportMeta & { env?: { BASE_URL?: string } }).env;

const GRID_SIZE = 100;
const GRID_COLOR = "rgba(255, 255, 255, 0.12)";
const AXIS_COLOR = "rgba(255, 255, 255, 0.3)";
const LABEL_COLOR = "rgba(255, 255, 255, 0.5)";
const LABEL_FONT = "22px 'Cascadia Code', 'Fira Code', 'Consolas', monospace";
const LABEL_PADDING = 8;
const DEFAULT_DURATION_MS = 3000;
const DEFAULT_FPS = 30;
const FIXED_STEP_SECONDS = 1 / 60;

type CaptureVideoOptions = {
    durationMs: number;
    fps: number;
};

type CaptureStopper = {
    stop(): void;
};

const normalizeLevelFile = (levelFile: string): string => {
    const trimmed = levelFile.trim();
    if (!trimmed) {
        throw new Error("levelFile is required");
    }
    return trimmed.endsWith(".json") ? trimmed : `${trimmed}.json`;
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

const wait = (ms: number): Promise<void> =>
    new Promise((resolve) => {
        window.setTimeout(resolve, ms);
    });

const nextAnimationFrame = (): Promise<void> =>
    new Promise((resolve) => {
        window.requestAnimationFrame(() => resolve());
    });

const drawGridOverlay = (ctx: CanvasRenderingContext2D, width: number, height: number): void => {
    ctx.save();

    ctx.lineWidth = 1;
    ctx.strokeStyle = GRID_COLOR;
    ctx.beginPath();
    for (let x = 0; x <= width; x += GRID_SIZE) {
        ctx.moveTo(x + 0.5, 0);
        ctx.lineTo(x + 0.5, height);
    }
    for (let y = 0; y <= height; y += GRID_SIZE) {
        ctx.moveTo(0, y + 0.5);
        ctx.lineTo(width, y + 0.5);
    }
    ctx.stroke();

    ctx.strokeStyle = AXIS_COLOR;
    ctx.beginPath();
    ctx.moveTo(0.5, 0);
    ctx.lineTo(0.5, height);
    ctx.moveTo(0, 0.5);
    ctx.lineTo(width, 0.5);
    ctx.stroke();

    ctx.fillStyle = LABEL_COLOR;
    ctx.font = LABEL_FONT;
    ctx.textBaseline = "top";
    ctx.textAlign = "left";

    for (let x = 0; x <= width; x += GRID_SIZE) {
        ctx.fillText(`${x}`, x + LABEL_PADDING, LABEL_PADDING);
    }

    for (let y = 0; y <= height; y += GRID_SIZE) {
        ctx.fillText(`${y}`, LABEL_PADDING, y + LABEL_PADDING);
    }

    ctx.restore();
};

const getSupportedMimeType = (): string => {
    const candidates = [
        "video/webm;codecs=vp9",
        "video/webm;codecs=vp8",
        "video/webm",
    ];

    for (const candidate of candidates) {
        if (MediaRecorder.isTypeSupported(candidate)) {
            return candidate;
        }
    }

    return "";
};

let readyPromise: Promise<void> | null = null;
let activeCaptureStopper: CaptureStopper | null = null;

const ensureCaptureReady = (): Promise<void> => {
    if (readyPromise) {
        return readyPromise;
    }

    readyPromise = new Promise((resolve) => {
        PreLoader.start();
        PreLoader.domReady();

        Canvas.domReady("captureVideoCanvas");
        if (!Canvas.element) {
            throw new Error("captureVideoCanvas element not found");
        }

        Canvas.element.width = resolution.CANVAS_WIDTH;
        Canvas.element.height = resolution.CANVAS_HEIGHT;
        Canvas.element.style.width = `${resolution.CANVAS_WIDTH}px`;
        Canvas.element.style.height = `${resolution.CANVAS_HEIGHT}px`;

        PreLoader.run(() => {
            document.body.dataset.captureReady = "1";
            resolve();
        });
    });

    return readyPromise;
};

const createScene = async (levelFile: string): Promise<GameScene> => {
    const normalized = normalizeLevelFile(levelFile);
    await ensureCaptureReady();

    const levelJson = await fetchLevelJson(normalized);
    LevelState.loadedMap = levelJson;
    LevelState.pack = 0;
    LevelState.level = 0;

    const scene = new GameScene();
    scene.gameController = {
        avgDelta: FIXED_STEP_SECONDS,
        frameBalance: 0,
        onLevelWon: () => {},
        onLevelLost: () => {},
    };

    const loadedMapKeys = LevelState.loadedMap ? Object.keys(LevelState.loadedMap) : [];
    if (!LevelState.loadedMap || loadedMapKeys.length === 0) {
        throw new Error("LevelState.loadedMap is empty before scene.show()");
    }

    scene.show();

    if (!scene.target && LevelState.loadedMap) {
        throw new Error(
            `Scene failed to load map objects for ${normalized}; loadedMapKeys=${Object.keys(LevelState.loadedMap).join(",")}`
        );
    }

    return scene;
};

const drawSceneFrame = (scene: GameScene): void => {
    try {
        scene.update(FIXED_STEP_SECONDS);
        scene.draw();
    } catch (error) {
        const details = {
            twoParts: scene.twoParts,
            noCandy: scene.noCandy,
            noCandyL: scene.noCandyL,
            noCandyR: scene.noCandyR,
            hasStar: Boolean(scene.star),
            hasStarL: Boolean(scene.starL),
            hasStarR: Boolean(scene.starR),
            hasCandy: Boolean(scene.candy),
            hasCandyL: Boolean(scene.candyL),
            hasCandyR: Boolean(scene.candyR),
            hasTarget: Boolean(scene.target),
            stars: scene.stars.length,
            bungees: scene.bungees.length,
            bubbles: scene.bubbles.length,
            pumps: scene.pumps.length,
        };
        const message = error instanceof Error ? error.message : String(error);
        throw new Error(`${message} | scene=${JSON.stringify(details)}`);
    }

    if (Canvas.context && Canvas.element) {
        drawGridOverlay(Canvas.context, Canvas.element.width, Canvas.element.height);
    }
};

const startSceneLoop = (scene: GameScene): CaptureStopper => {
    let rafId = 0;
    let stopped = false;

    const tick = () => {
        if (stopped) {
            return;
        }
        drawSceneFrame(scene);
        rafId = window.requestAnimationFrame(tick);
    };

    rafId = window.requestAnimationFrame(tick);

    return {
        stop() {
            stopped = true;
            if (rafId) {
                window.cancelAnimationFrame(rafId);
            }
        },
    };
};

const recordLevelBlob = async (
    levelFile: string,
    options: Partial<CaptureVideoOptions> = {}
): Promise<Blob> => {
    const durationMs = Math.max(250, options.durationMs ?? DEFAULT_DURATION_MS);
    const fps = Math.max(1, Math.round(options.fps ?? DEFAULT_FPS));
    const scene = await createScene(levelFile);
    const canvas = Canvas.element;

    if (!canvas) {
        throw new Error("captureVideoCanvas not ready");
    }
    if (typeof canvas.captureStream !== "function") {
        throw new Error("Canvas captureStream API is not available in this browser");
    }
    if (typeof MediaRecorder === "undefined") {
        throw new Error("MediaRecorder API is not available in this browser");
    }

    activeCaptureStopper?.stop();
    activeCaptureStopper = null;

    drawSceneFrame(scene);
    await nextAnimationFrame();

    const stream = canvas.captureStream(fps);
    const chunks: BlobPart[] = [];
    const mimeType = getSupportedMimeType();
    const recorder = mimeType
        ? new MediaRecorder(stream, {
              mimeType,
              videoBitsPerSecond: 4_000_000,
          })
        : new MediaRecorder(stream, {
              videoBitsPerSecond: 4_000_000,
          });

    const loop = startSceneLoop(scene);
    activeCaptureStopper = loop;

    const blobPromise = new Promise<Blob>((resolve, reject) => {
        recorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                chunks.push(event.data);
            }
        };
        recorder.onerror = () => {
            reject(new Error("MediaRecorder failed"));
        };
        recorder.onstop = () => {
            resolve(
                new Blob(chunks, {
                    type: recorder.mimeType || mimeType || "video/webm",
                })
            );
        };
    });

    try {
        recorder.start(250);
        await wait(durationMs);
        if (recorder.state !== "inactive") {
            recorder.stop();
        }
        return await blobPromise;
    } finally {
        loop.stop();
        activeCaptureStopper = null;
        stream.getTracks().forEach((track) => track.stop());
    }
};

const blobToDataUrl = (blob: Blob): Promise<string> =>
    new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || ""));
        reader.onerror = () => reject(reader.error ?? new Error("Failed to read blob"));
        reader.readAsDataURL(blob);
    });

const triggerDownload = (blob: Blob, filename: string): void => {
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = filename;
    anchor.style.display = "none";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
};

const params = new URLSearchParams(window.location.search);
const initialLevel = params.get("level");
const initialDurationMs = Number(params.get("duration") || DEFAULT_DURATION_MS);
const initialFps = Number(params.get("fps") || DEFAULT_FPS);
const autoDownload = params.get("download") === "1";

declare global {
    interface Window {
        captureLevelVideo?: (
            levelFile?: string,
            options?: Partial<CaptureVideoOptions>
        ) => Promise<string>;
        downloadLevelVideo?: (
            levelFile?: string,
            options?: Partial<CaptureVideoOptions>
        ) => Promise<string>;
    }
}

window.captureLevelVideo = async (levelFile?: string, options: Partial<CaptureVideoOptions> = {}) => {
    const target = levelFile || initialLevel;
    if (!target) {
        throw new Error("Missing level file");
    }

    const blob = await recordLevelBlob(target, options);
    return blobToDataUrl(blob);
};

window.downloadLevelVideo = async (
    levelFile?: string,
    options: Partial<CaptureVideoOptions> = {}
) => {
    const target = levelFile || initialLevel;
    if (!target) {
        throw new Error("Missing level file");
    }

    const normalized = normalizeLevelFile(target);
    const blob = await recordLevelBlob(normalized, options);
    const filename = normalized.replace(/\.json$/i, ".webm");
    triggerDownload(blob, filename);
    return filename;
};

if (initialLevel && autoDownload) {
    void window.downloadLevelVideo(initialLevel, {
        durationMs: Number.isFinite(initialDurationMs) ? initialDurationMs : DEFAULT_DURATION_MS,
        fps: Number.isFinite(initialFps) ? initialFps : DEFAULT_FPS,
    });
}
