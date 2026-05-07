import fs from "node:fs";
import fsAsync from "node:fs/promises";
import path from "node:path";
import { createCanvas, Image as CanvasImage } from "@napi-rs/canvas";
import type { LevelJson } from "@/types/json";

const GRID_SIZE = 100;
const GRID_COLOR = "rgba(255, 255, 255, 0.16)";
const AXIS_COLOR = "rgba(255, 255, 255, 0.28)";
const LABEL_COLOR = "rgba(255, 255, 255, 0.6)";
const LABEL_FONT = "22px 'Cascadia Code', 'Fira Code', 'Consolas', monospace";
const LABEL_PADDING = 8;

type DummyRect = {
    width: number;
    height: number;
    top: number;
    left: number;
    right: number;
    bottom: number;
};

class DummyClassList {
    add(..._names: string[]): void {}
    remove(..._names: string[]): void {}
    toggle(_name: string, _force?: boolean): void {}
    contains(_name: string): boolean {
        return false;
    }
}

type DummyStyle = Record<string, string>;

class DummyElement {
    style: DummyStyle = {};
    classList = new DummyClassList();
    children: DummyElement[] = [];
    width = 0;
    height = 0;

    addEventListener(_name: string, _handler?: (...args: unknown[]) => void): void {}
    removeEventListener(_name: string, _handler?: (...args: unknown[]) => void): void {}
    dispatchEvent(_event: Event): boolean {
        return false;
    }

    appendChild(child: DummyElement): void {
        this.children.push(child);
    }
    removeChild(_child: DummyElement): void {}
    setAttribute(_name: string, _value: string): void {}
    getBoundingClientRect(): DummyRect {
        return {
            width: this.width || 0,
            height: this.height || 0,
            top: 0,
            left: 0,
            right: this.width || 0,
            bottom: this.height || 0,
        };
    }
}

const publicRoot = path.resolve(process.cwd(), "public");

const resolveAssetPath = (url: string): string => {
    if (url.startsWith("data:")) {
        return url;
    }

    let pathname = url;
    if (/^https?:\/\//i.test(url)) {
        pathname = new URL(url).pathname;
    }
    if (pathname.startsWith("/")) {
        pathname = pathname.slice(1);
    }
    pathname = pathname.replace(/^\.\/+/, "");
    pathname = pathname.split(/[?#]/)[0] ?? pathname;
    pathname = decodeURIComponent(pathname);
    return path.join(publicRoot, pathname);
};

const decodeDataUrl = (dataUrl: string): Buffer => {
    const match = dataUrl.match(/^data:([^;,]+)?(;base64)?,(.*)$/);
    if (!match) {
        throw new Error("Invalid data URL");
    }
    const isBase64 = Boolean(match[2]);
    const data = match[3] ?? "";
    return isBase64 ? Buffer.from(data, "base64") : Buffer.from(decodeURIComponent(data), "utf8");
};

class NodeImage {
    private _src = "";
    decoding = "async";
    style: DummyStyle = {};
    classList = new DummyClassList();
    width = 0;
    height = 0;
    naturalWidth = 0;
    naturalHeight = 0;
    complete = false;
    onload: (() => void) | null = null;
    onerror: ((error: unknown) => void) | null = null;
    private listeners = new Map<string, Set<(...args: unknown[]) => void>>();
    __drawable: unknown = null;

    get src() {
        return this._src;
    }

    set src(value: string) {
        this.setSrc(value);
    }

    addEventListener(name: string, handler?: (...args: unknown[]) => void): void {
        if (!handler) {
            return;
        }
        if (!this.listeners.has(name)) {
            this.listeners.set(name, new Set());
        }
        this.listeners.get(name)!.add(handler);
    }

    removeEventListener(name: string, handler?: (...args: unknown[]) => void): void {
        if (!handler) {
            return;
        }
        this.listeners.get(name)?.delete(handler);
    }

    decode(): Promise<void> {
        return Promise.resolve();
    }

    private emit(name: string, event?: unknown) {
        const handlers = this.listeners.get(name);
        if (!handlers) {
            return;
        }
        for (const handler of handlers) {
            handler(event);
        }
    }

    setSrc(value: string) {
        this._src = value;
        this.complete = false;
        try {
            const buffer = value.startsWith("data:")
                ? decodeDataUrl(value)
                : fs.readFileSync(resolveAssetPath(value));
            const img = new CanvasImage();
            img.src = buffer;
            this.__drawable = img;
            this.width = img.width || 0;
            this.height = img.height || 0;
            this.naturalWidth = img.width || 0;
            this.naturalHeight = img.height || 0;
            this.complete = true;
            this.emit("load");
            this.onload?.();
        } catch (error) {
            this.emit("error", error);
            this.onerror?.(error);
        }
    }

    set srcValue(value: string) {
        this.setSrc(value);
    }
}

class NodeCanvasElement extends DummyElement {
    private canvas = createCanvas(1, 1);
    private ctx: unknown = null;
    private _width = 1;
    private _height = 1;
    __drawable: unknown = null;

    constructor(width = 1, height = 1) {
        super();
        this._width = width;
        this._height = height;
        this.canvas.width = width;
        this.canvas.height = height;
        this.__drawable = this.canvas;

        Object.defineProperty(this, "width", {
            get: () => this._width,
            set: (value: number) => {
                this._width = value;
                this.canvas.width = value;
            },
            configurable: true,
        });
        Object.defineProperty(this, "height", {
            get: () => this._height,
            set: (value: number) => {
                this._height = value;
                this.canvas.height = value;
            },
            configurable: true,
        });
    }

    getContext(type: string) {
        if (type !== "2d") {
            return null;
        }
        if (!this.ctx) {
            const ctx = this.canvas.getContext("2d");
            const originalDrawImage = ctx.drawImage.bind(ctx);
            ctx.drawImage = (...args: unknown[]) => {
                if (args[0] && typeof args[0] === "object" && "__drawable" in (args[0] as object)) {
                    args[0] = (args[0] as { __drawable: unknown }).__drawable;
                }
                return originalDrawImage(...(args as Parameters<typeof originalDrawImage>));
            };
            this.ctx = ctx;
        }
        return this.ctx as unknown as CanvasRenderingContext2D;
    }

    toBuffer(): Buffer {
        return this.canvas.toBuffer("image/png");
    }

    toDataURL(type = "image/png"): string {
        return this.canvas.toDataURL(type);
    }
}

const setupRenderDom = (mainCanvasRef: { current: NodeCanvasElement | null }) => {
    if ((globalThis as unknown as { __CTR_HEADLESS_RENDER__?: boolean }).__CTR_HEADLESS_RENDER__) {
        return;
    }

    (globalThis as unknown as { __CTR_HEADLESS_RENDER__?: boolean }).__CTR_HEADLESS_RENDER__ = true;

    const dummyDocument = {
        body: {
            appendChild() {},
            removeChild() {},
            classList: new DummyClassList(),
        },
        documentElement: new DummyElement(),
        fonts: {
            add() {},
        },
        readyState: "complete",
        addEventListener() {},
        removeEventListener() {},
        createElement(tag: string) {
            const lower = tag.toLowerCase();
            if (lower === "canvas") {
                return new NodeCanvasElement();
            }
            if (lower === "img" || lower === "image") {
                return new NodeImage();
            }
            return new DummyElement();
        },
        getElementById(id: string) {
            if (id === "captureCanvas" || id === "c" || id === "evalCanvas") {
                return mainCanvasRef.current;
            }
            return null;
        },
        querySelector() {
            return null;
        },
        querySelectorAll() {
            return [];
        },
    };

    const dummyWindow = globalThis as unknown as Record<string, unknown>;
    const defineProp = (key: string, value: unknown) => {
        Object.defineProperty(dummyWindow, key, {
            value,
            writable: true,
            configurable: true,
        });
    };

    defineProp("window", dummyWindow);
    defineProp("document", dummyDocument);
    defineProp("innerWidth", 1920);
    defineProp("innerHeight", 1080);
    defineProp("devicePixelRatio", 1);
    defineProp("location", {
        href: "http://localhost/",
        protocol: "http:",
        host: "localhost",
        search: "",
    });
    defineProp("navigator", { userAgent: "headless" });
    defineProp("addEventListener", () => {});
    defineProp("removeEventListener", () => {});
    defineProp("getComputedStyle", (el: { width?: number; height?: number }) => ({
        width: `${el?.width ?? 0}px`,
        height: `${el?.height ?? 0}px`,
        display: "block",
        opacity: "1",
    }));
    defineProp("requestAnimationFrame", (cb: (time: number) => void) =>
        setTimeout(() => cb(Date.now()), 0)
    );
    defineProp("cancelAnimationFrame", (id: number) => clearTimeout(id));
    defineProp("console", console);

    Object.defineProperty(globalThis, "document", {
        value: dummyDocument,
        writable: true,
        configurable: true,
    });
    Object.defineProperty(globalThis, "location", {
        value: dummyWindow.location,
        writable: true,
        configurable: true,
    });
    Object.defineProperty(globalThis, "navigator", {
        value: dummyWindow.navigator,
        writable: true,
        configurable: true,
    });

    (globalThis as unknown as { HTMLCanvasElement?: unknown }).HTMLCanvasElement =
        NodeCanvasElement;
    (globalThis as unknown as { HTMLImageElement?: unknown }).HTMLImageElement = NodeImage;
    (globalThis as unknown as { Image?: unknown }).Image = NodeImage;
    (globalThis as unknown as { ImageBitmap?: unknown }).ImageBitmap = class {};

    Object.defineProperty(globalThis, "fetch", {
        value: async (input: RequestInfo | URL) => {
            const url =
                typeof input === "string"
                    ? input
                    : input instanceof URL
                      ? input.href
                      : input.url;
            const filePath = resolveAssetPath(url);
            try {
                const data = await fsAsync.readFile(filePath);
                return new Response(data, { status: 200 });
            } catch {
                return new Response("Not Found", { status: 404 });
            }
        },
        writable: true,
        configurable: true,
    });

    if (typeof URL !== "undefined") {
        try {
            Object.defineProperty(URL, "createObjectURL", {
                value: undefined,
                writable: true,
                configurable: true,
            });
            Object.defineProperty(URL, "revokeObjectURL", {
                value: undefined,
                writable: true,
                configurable: true,
            });
        } catch {
            // ignore if URL properties are not configurable
        }
    }
};

const normalizeLevelFile = (levelFile: string): string => {
    const trimmed = levelFile.trim();
    if (!trimmed) {
        throw new Error("levelFile is required");
    }
    return trimmed.endsWith(".json") ? trimmed : `${trimmed}.json`;
};

const drawGridOverlay = (
    ctx: CanvasRenderingContext2D,
    width: number,
    height: number
): void => {
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

const getArg = (args: string[], name: string): string | null => {
    const idx = args.indexOf(`--${name}`);
    if (idx === -1) {
        return null;
    }
    return args[idx + 1] ?? null;
};

const main = async () => {
    const args = process.argv.slice(2);
    const outDirArg = getArg(args, "out");
    const outputDir = path.resolve(process.cwd(), outDirArg || "level_image");
    const levelDir = path.resolve(process.cwd(), "data", "task");

    const levels = (await fsAsync.readdir(levelDir))
        .filter((name) => name.endsWith(".json") && name !== "manifest.json")
        .sort();
    if (levels.length === 0) {
        console.error("No level JSON files found.");
        process.exit(1);
    }

    await fsAsync.mkdir(outputDir, { recursive: true });

    const mainCanvasRef: { current: NodeCanvasElement | null } = { current: null };
    setupRenderDom(mainCanvasRef);

    const [{ default: Canvas }, { default: PreLoader }, { default: LevelState }, { default: GameScene }, { default: resolution }] =
        await Promise.all([
            import("@/utils/Canvas"),
            import("@/resources/PreLoader"),
            import("@/game/LevelState"),
            import("@/GameScene"),
            import("@/resolution"),
        ]);

    const mainCanvas = new NodeCanvasElement(
        resolution.CANVAS_WIDTH,
        resolution.CANVAS_HEIGHT
    );
    mainCanvasRef.current = mainCanvas;

    Canvas.setTarget(mainCanvas as unknown as HTMLCanvasElement);

    await new Promise<void>((resolve) => {
        PreLoader.start();
        PreLoader.domReady();
        PreLoader.run(() => resolve());
    });

    for (let index = 0; index < levels.length; index += 1) {
        const levelFile = levels[index]!;
        const normalized = normalizeLevelFile(levelFile);
        const levelPath = path.resolve(levelDir, normalized);
        const text = await fsAsync.readFile(levelPath, "utf8");
        const levelJson = JSON.parse(text) as LevelJson;

        LevelState.loadedMap = levelJson;
        LevelState.pack = 0;
        LevelState.level = index;

        const scene = new GameScene();
        scene.gameController = {
            avgDelta: 1 / 60,
            frameBalance: 0,
            onLevelWon: () => {},
            onLevelLost: () => {},
        };

        scene.show();
        const sceneAny = scene as unknown as Record<string, unknown>;
        if (!sceneAny.back) {
            sceneAny.back = {
                updateWithCameraPos() {},
                draw() {},
            };
        }
        if (!sceneAny.support) {
            sceneAny.support = {
                draw() {},
            };
        }
        if (!sceneAny.target) {
            sceneAny.target = {
                draw() {},
                update() {},
            };
        }
        try {
            scene.update(1 / 60);
        } catch (error) {
            console.warn("Scene update failed for", normalized, error);
        }

        const ctx = Canvas.context;
        if (ctx) {
            ctx.clearRect(0, 0, mainCanvas.width, mainCanvas.height);
        }

        scene.draw();

        if (ctx) {
            drawGridOverlay(ctx, mainCanvas.width, mainCanvas.height);
        }

        const buffer = mainCanvas.toBuffer();
        const outPath = path.join(outputDir, normalized.replace(/\.json$/, ".png"));
        await fsAsync.writeFile(outPath, buffer);
        console.log(`Saved ${outPath}`);
    }
};

await main();
