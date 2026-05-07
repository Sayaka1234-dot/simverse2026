import fs from "node:fs/promises";
import path from "node:path";
import { createServer } from "vite";

const DEFAULT_PORT = 5173;
const DEFAULT_TIMEOUT_MS = 120000;

const getArg = (args, name) => {
    const idx = args.indexOf(`--${name}`);
    if (idx === -1) {
        return null;
    }
    return args[idx + 1] ?? null;
};

const hasFlag = (args, name) => args.includes(`--${name}`);

const printUsageAndExit = (code = 1) => {
    const stream = code === 0 ? process.stdout : process.stderr;
    stream.write(
        [
            "Usage: npm run eval:browser-batch -- --input <batch.json> --output <results.json>",
            "",
            "Options:",
            "  --headed              Show the browser while evaluating.",
            "  --reuse-page          Reuse one browser page for all cases. Faster, but less isolated.",
            "  --port <number>       Preferred Vite dev-server port.",
            "  --timeout-ms <number> Browser wait timeout in milliseconds.",
            "  --help                Show this message.",
            "",
        ].join("\n")
    );
    process.exit(code);
};

const toPositiveInteger = (value, fallback) => {
    const parsed = Number.parseInt(String(value ?? ""), 10);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
};

const normalizeBatchInput = (input) => {
    if (Array.isArray(input)) {
        return { cases: input, maxSeconds: undefined, stepSeconds: undefined };
    }
    return input;
};

const normalizeCommands = (commands) => {
    if (Array.isArray(commands)) {
        return commands.join("\n");
    }
    return String(commands ?? "");
};

const ensurePlaywright = async () => {
    try {
        return await import("playwright");
    } catch (error) {
        console.error("Playwright is required. Install it with: npm install -D playwright");
        throw error;
    }
};

const resolveOptions = () => {
    const args = process.argv.slice(2);
    if (hasFlag(args, "help")) {
        printUsageAndExit(0);
    }

    const inputPathArg = getArg(args, "input");
    if (!inputPathArg) {
        printUsageAndExit();
    }

    return {
        inputPath: path.resolve(process.cwd(), inputPathArg),
        outputPath: path.resolve(process.cwd(), getArg(args, "output") || "eval-results.json"),
        headed: hasFlag(args, "headed"),
        reusePage: hasFlag(args, "reuse-page"),
        port: toPositiveInteger(getArg(args, "port"), DEFAULT_PORT),
        timeoutMs: toPositiveInteger(getArg(args, "timeout-ms"), DEFAULT_TIMEOUT_MS),
    };
};

const formatError = (error) => (error instanceof Error ? error.message : String(error));

const main = async () => {
    const options = resolveOptions();
    const raw = await fs.readFile(options.inputPath, "utf8");
    const parsed = normalizeBatchInput(JSON.parse(raw));
    const cases = parsed.cases ?? [];

    if (!Array.isArray(cases) || cases.length === 0) {
        throw new Error("No cases found in input file.");
    }

    await fs.mkdir(path.dirname(options.outputPath), { recursive: true });

    const { chromium } = await ensurePlaywright();
    const server = await createServer({
        root: process.cwd(),
        logLevel: "error",
        server: {
            port: options.port,
            strictPort: false,
        },
    });

    await server.listen();
    const baseUrl = server.resolvedUrls?.local?.[0] ?? `http://localhost:${options.port}`;

    const browser = await chromium.launch({ headless: !options.headed });
    const context = await browser.newContext({
        viewport: { width: 1920, height: 1080 },
        deviceScaleFactor: 1,
    });
    const results = [];
    let wonCount = 0;
    let lostCount = 0;
    let timeoutCount = 0;

    const evaluateCase = async (entry, reusablePage = null) => {
        const page = reusablePage ?? (await context.newPage());
        page.setDefaultTimeout(options.timeoutMs);

        const pageErrors = [];
        const consoleErrors = [];
        page.on("pageerror", (error) => pageErrors.push(String(error)));
        page.on("console", (msg) => {
            if (msg.type() === "error" || msg.type() === "warning") {
                consoleErrors.push(`[${msg.type()}] ${msg.text()}`);
            }
        });

        try {
            if (!reusablePage) {
                await page.goto(`${baseUrl}/eval.html`, { waitUntil: "networkidle" });
                await page.waitForFunction(() => typeof window.evalLevel === "function");
            }

            const merged = {
                ...entry,
                commands: normalizeCommands(entry.commands),
                maxSeconds: entry.maxSeconds ?? parsed.maxSeconds,
                stepSeconds: entry.stepSeconds ?? parsed.stepSeconds,
            };

            const result = await page.evaluate(async (browserCase) => {
                if (typeof window.evalLevel !== "function") {
                    throw new Error("window.evalLevel is not available.");
                }
                return await window.evalLevel(browserCase.level, browserCase.commands, {
                    maxSeconds: browserCase.maxSeconds,
                    stepSeconds: browserCase.stepSeconds,
                });
            }, merged);

            return {
                level: entry.level,
                ...result,
                commands: entry.commands,
            };
        } catch (error) {
            return {
                level: entry.level,
                won: false,
                stars: 0,
                time: 0,
                score: 0,
                reason: "timeout",
                frames: 0,
                commands: entry.commands,
                error: formatError(error),
                pageErrors: [...pageErrors],
                consoleErrors: [...consoleErrors],
            };
        } finally {
            if (!reusablePage) {
                await page.close();
            }
        }
    };

    try {
        let reusablePage = null;
        if (options.reusePage) {
            reusablePage = await context.newPage();
            reusablePage.setDefaultTimeout(options.timeoutMs);
            await reusablePage.goto(`${baseUrl}/eval.html`, { waitUntil: "networkidle" });
            await reusablePage.waitForFunction(() => typeof window.evalLevel === "function");
        }

        try {
            for (const entry of cases) {
                const result = await evaluateCase(entry, reusablePage);
                results.push(result);

                if (result.won) {
                    wonCount += 1;
                } else if (result.reason === "lost") {
                    lostCount += 1;
                } else {
                    timeoutCount += 1;
                }
            }
        } finally {
            if (reusablePage) {
                await reusablePage.close();
            }
        }
    } finally {
        await context.close();
        await browser.close();
        await server.close();
    }

    const summary = {
        total: results.length,
        won: wonCount,
        lost: lostCount,
        timeout: timeoutCount,
        backend: "browser",
        pageIsolation: options.reusePage ? "reuse-page" : "fresh-page-per-case",
    };

    await fs.writeFile(options.outputPath, JSON.stringify({ summary, results }, null, 2), "utf8");
    console.log(`Wrote browser results to ${options.outputPath}`);
};

await main().catch((error) => {
    console.error(formatError(error));
    process.exit(1);
});
