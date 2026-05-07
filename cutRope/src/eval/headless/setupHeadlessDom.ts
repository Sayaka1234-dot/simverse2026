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

const createDummyContext = (canvas: DummyCanvas) => {
    return {
        canvas,
        fillStyle: "",
        strokeStyle: "",
        globalAlpha: 1,
        globalCompositeOperation: "source-over",
        font: "",
        lineWidth: 1,
        save() {},
        restore() {},
        setTransform() {},
        translate() {},
        rotate() {},
        scale() {},
        beginPath() {},
        closePath() {},
        moveTo() {},
        lineTo() {},
        rect() {},
        arc() {},
        fill() {},
        stroke() {},
        clearRect() {},
        fillRect() {},
        drawImage() {},
        clip() {},
        measureText(text: string) {
            return { width: text ? text.length * 10 : 0 };
        },
        fillText() {},
        strokeText() {},
    };
};

class DummyCanvas extends DummyElement {
    private readonly ctx: ReturnType<typeof createDummyContext>;

    constructor(width = 4096, height = 4096) {
        super();
        this.width = width;
        this.height = height;
        this.ctx = createDummyContext(this);
    }

    getContext(type: string) {
        if (type === "2d") {
            return this.ctx;
        }
        return null;
    }

    toDataURL(_type?: string): string {
        return "data:image/png;base64,";
    }
}

class DummyImage extends DummyElement {
    naturalWidth = 4096;
    naturalHeight = 4096;
    complete = true;
    src = "";

    constructor(width = 4096, height = 4096) {
        super();
        this.width = width;
        this.height = height;
        this.naturalWidth = width;
        this.naturalHeight = height;
    }
}

const createLocalStorage = () => {
    const store = new Map<string, string>();
    return {
        get length() {
            return store.size;
        },
        clear() {
            store.clear();
        },
        getItem(key: string) {
            return store.has(key) ? store.get(key)! : null;
        },
        key(index: number) {
            return Array.from(store.keys())[index] ?? null;
        },
        removeItem(key: string) {
            store.delete(key);
        },
        setItem(key: string, value: string) {
            store.set(key, value);
        },
    };
};

export const setupHeadlessDom = () => {
    if ((globalThis as unknown as { __CTR_HEADLESS__?: boolean }).__CTR_HEADLESS__) {
        return;
    }

    (globalThis as unknown as { __CTR_HEADLESS__?: boolean }).__CTR_HEADLESS__ = true;

    const dummyCanvas = new DummyCanvas();
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
                return new DummyCanvas();
            }
            if (lower === "img" || lower === "image") {
                return new DummyImage();
            }
            return new DummyElement();
        },
        getElementById(id: string) {
            if (id === "c" || id === "evalCanvas") {
                return dummyCanvas;
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
    dummyWindow.window = dummyWindow;
    dummyWindow.document = dummyDocument;
    dummyWindow.innerWidth = 1920;
    dummyWindow.innerHeight = 1080;
    dummyWindow.devicePixelRatio = 1;
    dummyWindow.location = { href: "http://localhost/", search: "" };
    Object.defineProperty(dummyWindow, 'navigator', {
        value: { userAgent: "headless" },
        writable: true,
        configurable: true,
    });
    dummyWindow.addEventListener = () => {};
    dummyWindow.removeEventListener = () => {};
    dummyWindow.getComputedStyle = (el: { width?: number; height?: number }) => ({
        width: `${el?.width ?? 0}px`,
        height: `${el?.height ?? 0}px`,
        display: "block",
        opacity: "1",
    });
    dummyWindow.requestAnimationFrame = (cb: (time: number) => void) =>
        setTimeout(() => cb(Date.now()), 0);
    dummyWindow.cancelAnimationFrame = (id: number) => clearTimeout(id);
    dummyWindow.localStorage = createLocalStorage();
    dummyWindow.console = console;

    (globalThis as unknown as { document?: unknown }).document = dummyDocument;
    (globalThis as unknown as { location?: unknown }).location = dummyWindow.location;
    (globalThis as unknown as { navigator?: unknown }).navigator = dummyWindow.navigator;
    (globalThis as unknown as { localStorage?: unknown }).localStorage =
        dummyWindow.localStorage;

    (globalThis as unknown as { HTMLCanvasElement?: unknown }).HTMLCanvasElement = DummyCanvas;
    (globalThis as unknown as { HTMLImageElement?: unknown }).HTMLImageElement = DummyImage;
    (globalThis as unknown as { Image?: unknown }).Image = DummyImage;
    (globalThis as unknown as { ImageBitmap?: unknown }).ImageBitmap = class {};
};

export type { DummyCanvas, DummyImage };
