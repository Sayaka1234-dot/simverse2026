import fs from "node:fs/promises";
import path from "node:path";
import { createServer } from "vite";

type CaptureOptions = {
    outputDir: string;
    levelDir: string;
};

const getArg = (args: string[], name: string): string | null => {
    const idx = args.indexOf(`--${name}`);
    if (idx === -1) {
        return null;
    }
    return args[idx + 1] ?? null;
};

const printUsageAndExit = () => {
    console.error("Usage: npm run capture:levels -- --out <dir>");
    process.exit(1);
};

const resolveOptions = (): CaptureOptions => {
    const args = process.argv.slice(2);
    const outDirArg = getArg(args, "out");
    const outputDir = path.resolve(process.cwd(), outDirArg || "level_image");
    const levelDir = path.resolve(process.cwd(), "data", "task");
    return { outputDir, levelDir };
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

const listLevels = async (levelDir: string): Promise<string[]> => {
    const entries = await fs.readdir(levelDir);
    const compareLevelNames = (a: string, b: string): number => {
        const matchA = a.match(/^(\d+)-(\d+)\.json$/);
        const matchB = b.match(/^(\d+)-(\d+)\.json$/);
        if (!matchA || !matchB) {
            return a.localeCompare(b);
        }
        const boxDiff = Number.parseInt(matchA[1]!, 10) - Number.parseInt(matchB[1]!, 10);
        if (boxDiff !== 0) {
            return boxDiff;
        }
        return Number.parseInt(matchA[2]!, 10) - Number.parseInt(matchB[2]!, 10);
    };

    return entries
        .filter((name) => name.endsWith(".json") && name !== "manifest.json")
        .sort(compareLevelNames);
};

const main = async () => {
    const { outputDir, levelDir } = resolveOptions();

    const levels = await listLevels(levelDir);
    if (levels.length === 0) {
        console.error("No level JSON files found.");
        process.exit(1);
    }

    await fs.mkdir(outputDir, { recursive: true });

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
    const page = await browser.newPage({
        viewport: { width: 1920, height: 1080 },
        deviceScaleFactor: 1,
    });

    await page.goto(`${baseUrl}/capture.html`, { waitUntil: "networkidle" });
    await page.waitForFunction(() => typeof window.captureLevel === "function");

    for (const levelFile of levels) {
        const dataUrl = await page.evaluate(async (level) => {
            return await window.captureLevel?.(level);
        }, levelFile);

        if (!dataUrl || typeof dataUrl !== "string") {
            throw new Error(`Failed to capture ${levelFile}`);
        }

        const match = dataUrl.match(/^data:image\/png;base64,(.+)$/);
        if (!match) {
            throw new Error(`Invalid data URL for ${levelFile}`);
        }

        const buffer = Buffer.from(match[1], "base64");
        const outPath = path.join(outputDir, levelFile.replace(/\.json$/, ".png"));
        await fs.writeFile(outPath, buffer);
        console.log(`Saved ${outPath}`);
    }

    await browser.close();
    await server.close();
};

await main();
