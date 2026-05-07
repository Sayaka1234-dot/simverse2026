import fs from "node:fs/promises";
import path from "node:path";
import { createServer } from "vite";

const getArg = (args, name) => {
    const idx = args.indexOf(`--${name}`);
    if (idx === -1) {
        return null;
    }
    return args[idx + 1] ?? null;
};

const hasFlag = (args, name) => args.includes(`--${name}`);

const normalizeLevelFile = (level) => {
    const trimmed = level.trim();
    if (!trimmed) {
        throw new Error("level name cannot be empty");
    }
    return trimmed.endsWith(".json") ? trimmed : `${trimmed}.json`;
};

const toPositiveNumber = (value, fallback) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
};

const toPositiveInteger = (value) => {
    if (!value) {
        return null;
    }
    const parsed = Number.parseInt(value, 10);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
};

const printUsageAndExit = () => {
    console.error(
        "Usage: npm run capture:videos -- [--out data/video] [--seconds 3] [--fps 30] [--level 000.json,001.json] [--from 050.json] [--limit 10] [--force]"
    );
    process.exit(1);
};

const resolveOptions = () => {
    const args = process.argv.slice(2);
    if (hasFlag(args, "help")) {
        printUsageAndExit();
    }

    const outDirArg = getArg(args, "out");
    const outputDir = path.resolve(process.cwd(), outDirArg || "data/video");
    const levelDir = path.resolve(process.cwd(), "data", "task");
    const seconds = toPositiveNumber(getArg(args, "seconds"), 3);
    const fps = Math.max(1, Math.round(toPositiveNumber(getArg(args, "fps"), 30)));
    const limit = toPositiveInteger(getArg(args, "limit"));
    const levelArg = getArg(args, "level");
    const onlyLevels = levelArg
        ? levelArg
              .split(",")
              .map((name) => normalizeLevelFile(name))
              .filter(Boolean)
        : null;
    const fromLevelArg = getArg(args, "from");
    const fromLevel = fromLevelArg ? normalizeLevelFile(fromLevelArg) : null;
    const force = hasFlag(args, "force");

    return {
        outputDir,
        levelDir,
        seconds,
        fps,
        onlyLevels,
        fromLevel,
        limit,
        force,
    };
};

const ensurePlaywright = async () => {
    try {
        return await import("playwright");
    } catch (error) {
        console.error(
            "Playwright is required. Install it with: npm install -D playwright"
        );
        throw error;
    }
};

const compareLevelNames = (a, b) => {
    const sequentialA = a.match(/^(\d+)\.json$/);
    const sequentialB = b.match(/^(\d+)\.json$/);
    if (sequentialA && sequentialB) {
        return Number.parseInt(sequentialA[1], 10) - Number.parseInt(sequentialB[1], 10);
    }

    const matchA = a.match(/^(\d+)-(\d+)\.json$/);
    const matchB = b.match(/^(\d+)-(\d+)\.json$/);
    if (!matchA || !matchB) {
        return a.localeCompare(b);
    }
    const boxDiff = Number.parseInt(matchA[1], 10) - Number.parseInt(matchB[1], 10);
    if (boxDiff !== 0) {
        return boxDiff;
    }
    return Number.parseInt(matchA[2], 10) - Number.parseInt(matchB[2], 10);
};

const listLevels = async (levelDir) => {
    const entries = await fs.readdir(levelDir);
    return entries
        .filter((name) => name.endsWith(".json") && name !== "manifest.json")
        .sort(compareLevelNames);
};

const fileExists = async (targetPath) => {
    try {
        await fs.access(targetPath);
        return true;
    } catch {
        return false;
    }
};

const dataUrlToBuffer = (dataUrl) => {
    if (typeof dataUrl !== "string") {
        throw new Error(
            `Browser recorder returned a non-string value: ${JSON.stringify(dataUrl)}`
        );
    }

    const commaIndex = dataUrl.indexOf(",");
    if (commaIndex === -1 || !dataUrl.startsWith("data:")) {
        throw new Error(`Invalid data URL returned from browser recorder: ${dataUrl.slice(0, 120)}`);
    }

    const header = dataUrl.slice(0, commaIndex);
    const data = dataUrl.slice(commaIndex + 1);
    const isBase64 = /;base64$/i.test(header);
    return isBase64
        ? Buffer.from(data, "base64")
        : Buffer.from(decodeURIComponent(data), "utf8");
};

const waitForAppReady = async (page) => {
    try {
        await page.waitForFunction(() => {
            const gameArea = document.getElementById("gameArea");
            return (
                Boolean(window.ctrAutomation?.appReady) &&
                gameArea instanceof HTMLElement &&
                getComputedStyle(gameArea).display !== "none"
            );
        }, null, {
            timeout: 60000,
        });
    } catch (error) {
        const state = await page.evaluate(() => {
            const gameArea = document.getElementById("gameArea");
            return {
                href: window.location.href,
                title: document.title,
                appReady: Boolean(window.ctrAutomation?.appReady),
                hasGameArea: gameArea instanceof HTMLElement,
                gameAreaDisplay:
                    gameArea instanceof HTMLElement ? getComputedStyle(gameArea).display : null,
                bodyClass: document.body.className,
            };
        });

        throw new Error(`App page did not become ready in time: ${JSON.stringify(state)} | ${error}`);
    }

    await page.waitForTimeout(500);
};

const waitForLevelReady = async (page, expectedLevelNumber, previousStartCount) => {
    try {
        await page.waitForFunction(({ expectedLevelNumber, previousStartCount }) => {
            const canvas = document.getElementById("c");
            const grid = document.getElementById("gridOverlay");
            const gameArea = document.getElementById("gameArea");
            const gameBtnTray = document.getElementById("gameBtnTray");
            const automation = window.ctrAutomation;

            if (!(canvas instanceof HTMLCanvasElement)) {
                return false;
            }
            if (!(grid instanceof HTMLCanvasElement)) {
                return false;
            }
            if (!(gameArea instanceof HTMLElement)) {
                return false;
            }

            if (canvas.width <= 0 || canvas.height <= 0) {
                return false;
            }

            return (
                Boolean(automation?.appReady) &&
                automation?.lastStartedLevel === expectedLevelNumber &&
                (automation?.startLevelCount ?? 0) > previousStartCount &&
                getComputedStyle(gameArea).display !== "none" &&
                gameBtnTray instanceof HTMLElement &&
                getComputedStyle(gameBtnTray).display !== "none"
            );
        }, {
            expectedLevelNumber,
            previousStartCount,
        }, {
            timeout: 60000,
        });
    } catch (error) {
        const state = await page.evaluate(() => {
            const canvas = document.getElementById("c");
            const grid = document.getElementById("gridOverlay");
            const gameArea = document.getElementById("gameArea");
            const levelPanel = document.getElementById("levelPanel");
            const gameBtnTray = document.getElementById("gameBtnTray");

            return {
                href: window.location.href,
                title: document.title,
                hasCanvas: canvas instanceof HTMLCanvasElement,
                canvasSize:
                    canvas instanceof HTMLCanvasElement
                        ? { width: canvas.width, height: canvas.height }
                        : null,
                hasGrid: grid instanceof HTMLCanvasElement,
                hasGameArea: gameArea instanceof HTMLElement,
                gameAreaDisplay:
                    gameArea instanceof HTMLElement ? getComputedStyle(gameArea).display : null,
                gameAreaOpacity:
                    gameArea instanceof HTMLElement ? getComputedStyle(gameArea).opacity : null,
                levelPanelDisplay:
                    levelPanel instanceof HTMLElement ? getComputedStyle(levelPanel).display : null,
                gameBtnTrayDisplay:
                    gameBtnTray instanceof HTMLElement
                        ? getComputedStyle(gameBtnTray).display
                        : null,
                automation: window.ctrAutomation
                    ? {
                          appReady: window.ctrAutomation.appReady,
                          lastStartedLevel: window.ctrAutomation.lastStartedLevel,
                          startLevelCount: window.ctrAutomation.startLevelCount,
                      }
                    : null,
                bodyClass: document.body.className,
            };
        });

        throw new Error(
            `Level page did not become ready in time: ${JSON.stringify(state)} | ${error}`
        );
    }

    await page.waitForTimeout(1000);
};

const recordLevelFromPage = async (page, durationMs, fps) =>
    page.evaluate(
        async ({ durationMs, fps }) => {
            const mainCanvas = document.getElementById("c");
            const gridCanvas = document.getElementById("gridOverlay");

            if (!(mainCanvas instanceof HTMLCanvasElement)) {
                throw new Error("Main game canvas (#c) not found");
            }

            const compositeCanvas = document.createElement("canvas");
            compositeCanvas.width = mainCanvas.width;
            compositeCanvas.height = mainCanvas.height;

            const ctx = compositeCanvas.getContext("2d");
            if (!ctx) {
                throw new Error("Failed to create composite canvas context");
            }

            if (typeof compositeCanvas.captureStream !== "function") {
                throw new Error("Canvas captureStream API is not available in this browser");
            }
            if (typeof MediaRecorder === "undefined") {
                throw new Error("MediaRecorder API is not available in this browser");
            }

            let rafId = 0;
            let stopped = false;

            const render = () => {
                if (stopped) {
                    return;
                }

                ctx.clearRect(0, 0, compositeCanvas.width, compositeCanvas.height);
                ctx.drawImage(mainCanvas, 0, 0);

                if (gridCanvas instanceof HTMLCanvasElement) {
                    ctx.drawImage(gridCanvas, 0, 0);
                }

                rafId = window.requestAnimationFrame(render);
            };

            render();
            await new Promise((resolve) => window.requestAnimationFrame(() => resolve()));

            const mimeCandidates = [
                "video/webm;codecs=vp9",
                "video/webm;codecs=vp8",
                "video/webm",
            ];
            const mimeType =
                mimeCandidates.find((candidate) => MediaRecorder.isTypeSupported(candidate)) || "";

            const stream = compositeCanvas.captureStream(fps);
            const chunks = [];
            const recorder = mimeType
                ? new MediaRecorder(stream, {
                      mimeType,
                      videoBitsPerSecond: 4000000,
                  })
                : new MediaRecorder(stream, {
                      videoBitsPerSecond: 4000000,
                  });

            const blob = await new Promise((resolve, reject) => {
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

                recorder.start(250);
                window.setTimeout(() => {
                    if (recorder.state !== "inactive") {
                        recorder.stop();
                    }
                }, durationMs);
            });

            stopped = true;
            if (rafId) {
                window.cancelAnimationFrame(rafId);
            }
            stream.getTracks().forEach((track) => track.stop());

            return await new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(String(reader.result || ""));
                reader.onerror = () =>
                    reject(reader.error || new Error("Failed to convert blob to data URL"));
                reader.readAsDataURL(blob);
            });
        },
        { durationMs, fps }
    );

const selectLevels = async (allLevels, options) => {
    let result = allLevels;

    if (options.onlyLevels) {
        const missing = options.onlyLevels.filter((level) => !allLevels.includes(level));
        if (missing.length > 0) {
            throw new Error(`Unknown level files: ${missing.join(", ")}`);
        }
        result = options.onlyLevels;
    }

    if (options.fromLevel) {
        const startIndex = result.indexOf(options.fromLevel);
        if (startIndex === -1) {
            throw new Error(`Cannot find start level: ${options.fromLevel}`);
        }
        result = result.slice(startIndex);
    }

    if (options.limit != null) {
        result = result.slice(0, options.limit);
    }

    return result;
};

const main = async () => {
    const options = resolveOptions();
    const allLevels = await listLevels(options.levelDir);
    const levels = await selectLevels(allLevels, options);

    if (levels.length === 0) {
        console.error("No level JSON files selected.");
        process.exit(1);
    }

    await fs.mkdir(options.outputDir, { recursive: true });

    const { chromium } = await ensurePlaywright();

    const server = await createServer({
        root: process.cwd(),
        logLevel: "error",
        server: {
            port: 5173,
            strictPort: false,
        },
    });

    await server.listen();
    const baseUrl = server.resolvedUrls?.local?.[0] ?? "http://localhost:5173";

    const browser = await chromium.launch();
    const context = await browser.newContext({
        viewport: { width: 1920, height: 1080 },
        deviceScaleFactor: 1,
    });
    const page = await context.newPage();
    const pageErrors = [];
    const consoleErrors = [];

    page.on("pageerror", (error) => {
        pageErrors.push(String(error));
    });

    page.on("console", (msg) => {
        if (msg.type() === "error" || msg.type() === "warning") {
            consoleErrors.push(`[${msg.type()}] ${msg.text()}`);
        }
    });

    const durationMs = Math.round(options.seconds * 1000);
    const levelNumberByFile = new Map(allLevels.map((levelFile, index) => [levelFile, index + 1]));

    try {
        console.log(
            `Capturing ${levels.length} level video(s) to ${options.outputDir} (${options.seconds}s, ${options.fps}fps)`
        );

        await page.goto(`${baseUrl}/`, { waitUntil: "networkidle" });
        await waitForAppReady(page);

        for (const levelFile of levels) {
            const outPath = path.join(options.outputDir, levelFile.replace(/\.json$/i, ".webm"));
            if (!options.force && (await fileExists(outPath))) {
                console.log(`Skipping ${levelFile} (already exists)`);
                continue;
            }

            const levelNumber = levelNumberByFile.get(levelFile);
            if (!levelNumber) {
                throw new Error(`Missing level number mapping for ${levelFile}`);
            }

            pageErrors.length = 0;
            consoleErrors.length = 0;
            try {
                const previousStartCount = await page.evaluate(
                    () => window.ctrAutomation?.startLevelCount ?? 0
                );
                await page.evaluate((levelNumber) => {
                    return window.ctrAutomation?.startLevel(levelNumber);
                }, levelNumber);
                await waitForLevelReady(page, levelNumber, previousStartCount);
                await page.waitForTimeout(300);
            } catch (error) {
                throw new Error(
                    `${error}\nPageErrors=${JSON.stringify(pageErrors)}\nConsole=${JSON.stringify(consoleErrors)}`
                );
            }

            const dataUrl = await recordLevelFromPage(page, durationMs, options.fps);
            const buffer = dataUrlToBuffer(dataUrl);
            await fs.writeFile(outPath, buffer);
            console.log(`Saved ${outPath}`);
        }
    } finally {
        await page.close();
        await context.close();
        await browser.close();
        await server.close();
    }
};

await main();
