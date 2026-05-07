import fs from "node:fs/promises";
import path from "node:path";
import { setupHeadlessDom } from "../src/eval/headless/setupHeadlessDom";

setupHeadlessDom();

const { evaluateLevelHeadless } = await import("../src/eval/headless/HeadlessEvaluator");

type BatchCase = {
    level: string;
    commands: string | string[];
    maxSeconds?: number;
    stepSeconds?: number;
};

type BatchInput =
    | BatchCase[]
    | {
          cases: BatchCase[];
          maxSeconds?: number;
          stepSeconds?: number;
      };

const getArg = (args: string[], name: string): string | null => {
    const idx = args.indexOf(`--${name}`);
    if (idx === -1) {
        return null;
    }
    const value = args[idx + 1];
    return value ?? null;
};

const printUsageAndExit = () => {
    console.error(
        "Usage: npm run eval:batch -- --input <batch.json> --output <results.json>"
    );
    process.exit(1);
};

const normalizeBatchInput = (input: BatchInput) => {
    if (Array.isArray(input)) {
        return { cases: input, maxSeconds: undefined, stepSeconds: undefined };
    }
    return input;
};

const args = process.argv.slice(2);
const inputPathArg = getArg(args, "input");
const outputPathArg = getArg(args, "output");

if (!inputPathArg) {
    printUsageAndExit();
}

const inputPath = path.resolve(process.cwd(), inputPathArg);
const outputPath = path.resolve(process.cwd(), outputPathArg || "eval-results.json");

const raw = await fs.readFile(inputPath, "utf8");
const parsed = normalizeBatchInput(JSON.parse(raw) as BatchInput);
const cases = parsed.cases ?? [];

if (!Array.isArray(cases) || cases.length === 0) {
    console.error("No cases found in input file.");
    process.exit(1);
}

const results = [];
let wonCount = 0;
let lostCount = 0;
let timeoutCount = 0;

for (const entry of cases) {
    const merged = {
        ...entry,
        maxSeconds: entry.maxSeconds ?? parsed.maxSeconds,
        stepSeconds: entry.stepSeconds ?? parsed.stepSeconds,
    };

    try {
        const result = await evaluateLevelHeadless(merged);
        results.push({ ...result, commands: entry.commands });

        if (result.reason === "won") {
            wonCount += 1;
        } else if (result.reason === "lost") {
            lostCount += 1;
        } else {
            timeoutCount += 1;
        }
    } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        results.push({
            level: entry.level,
            won: false,
            stars: 0,
            time: 0,
            score: 0,
            reason: "timeout",
            frames: 0,
            commands: entry.commands,
            error: message,
        });
        timeoutCount += 1;
    }
}

const summary = {
    total: results.length,
    won: wonCount,
    lost: lostCount,
    timeout: timeoutCount,
};

await fs.writeFile(
    outputPath,
    JSON.stringify({ summary, results }, null, 2),
    "utf8"
);

console.log(`Wrote results to ${outputPath}`);
