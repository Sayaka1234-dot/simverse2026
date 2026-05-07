import fs from "node:fs/promises";
import path from "node:path";
import { spawn } from "node:child_process";

const getArg = (args, name) => {
    const index = args.indexOf(`--${name}`);
    return index === -1 ? null : args[index + 1] ?? null;
};

const hasFlag = (args, name) => args.includes(`--${name}`);

const normalizeVideoName = (name) => {
    const trimmed = String(name ?? "").trim();
    if (!trimmed) {
        throw new Error("video name cannot be empty");
    }
    return trimmed.endsWith(".webm") ? trimmed : `${trimmed.replace(/\.mp4$/i, "")}.webm`;
};

const compareNames = (a, b) => {
    const aMatch = a.match(/^(\d+)\.webm$/);
    const bMatch = b.match(/^(\d+)\.webm$/);
    if (aMatch && bMatch) {
        return Number.parseInt(aMatch[1], 10) - Number.parseInt(bMatch[1], 10);
    }
    return a.localeCompare(b);
};

const fileExists = async (targetPath) => {
    try {
        await fs.access(targetPath);
        return true;
    } catch {
        return false;
    }
};

const printUsageAndExit = () => {
    console.error(
        "Usage: node scripts/convert-level-videos-to-mp4.mjs [--input level_video] [--out data/video] [--ffmpeg ffmpeg] [--video-codec libx264] [--video-bitrate 4000k] [--fps 30] [--level 000.webm,001.webm] [--limit 10] [--force]"
    );
    process.exit(0);
};

const toPositiveInteger = (value) => {
    if (!value) {
        return null;
    }
    const parsed = Number.parseInt(value, 10);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
};

const resolveOptions = () => {
    const args = process.argv.slice(2);
    if (hasFlag(args, "help")) {
        printUsageAndExit();
    }

    const levelArg = getArg(args, "level");
    const onlyVideos = levelArg
        ? levelArg
              .split(",")
              .map((name) => normalizeVideoName(name))
              .filter(Boolean)
        : null;

    return {
        inputDir: path.resolve(process.cwd(), getArg(args, "input") || "level_video"),
        outputDir: path.resolve(process.cwd(), getArg(args, "out") || "data/video"),
        ffmpeg: getArg(args, "ffmpeg") || process.env.FFMPEG_PATH || "ffmpeg",
        videoCodec: getArg(args, "video-codec") || "libx264",
        videoBitrate: getArg(args, "video-bitrate") || "4000k",
        fps: toPositiveInteger(getArg(args, "fps")) || 30,
        onlyVideos,
        limit: toPositiveInteger(getArg(args, "limit")),
        force: hasFlag(args, "force"),
    };
};

const listVideos = async (inputDir, onlyVideos, limit) => {
    let videos = onlyVideos;
    if (!videos) {
        videos = (await fs.readdir(inputDir)).filter((name) => name.endsWith(".webm")).sort(compareNames);
    }
    if (limit !== null) {
        videos = videos.slice(0, limit);
    }
    return videos;
};

const runFfmpeg = (ffmpeg, inputPath, outputPath, options) =>
    new Promise((resolve, reject) => {
        const args = [
            options.force ? "-y" : "-n",
            "-i",
            inputPath,
            "-c:v",
            options.videoCodec,
            "-b:v",
            options.videoBitrate,
            "-r",
            String(options.fps),
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-an",
            outputPath,
        ];
        const child = spawn(ffmpeg, args, {
            cwd: process.cwd(),
            stdio: ["ignore", "pipe", "pipe"],
        });

        let stdout = "";
        let stderr = "";
        child.stdout.on("data", (chunk) => {
            stdout += chunk.toString();
        });
        child.stderr.on("data", (chunk) => {
            stderr += chunk.toString();
        });
        child.on("error", (error) => {
            reject(error);
        });
        child.on("close", (code) => {
            if (code === 0) {
                resolve();
                return;
            }
            reject(
                new Error(
                    `ffmpeg exited with code ${code} for ${path.basename(inputPath)}\n${stdout}\n${stderr}`.trim()
                )
            );
        });
    });

const main = async () => {
    const options = resolveOptions();
    await fs.mkdir(options.outputDir, { recursive: true });
    const videos = await listVideos(options.inputDir, options.onlyVideos, options.limit);
    if (videos.length === 0) {
        throw new Error(`No .webm files found in ${options.inputDir}`);
    }

    let converted = 0;
    let skipped = 0;
    for (const videoName of videos) {
        const inputPath = path.join(options.inputDir, videoName);
        const outputPath = path.join(options.outputDir, videoName.replace(/\.webm$/i, ".mp4"));
        if (!(await fileExists(inputPath))) {
            throw new Error(`Input video not found: ${inputPath}`);
        }
        if (!options.force && (await fileExists(outputPath))) {
            console.log(`skip existing ${path.relative(process.cwd(), outputPath)}`);
            skipped += 1;
            continue;
        }
        console.log(`convert ${path.relative(process.cwd(), inputPath)} -> ${path.relative(process.cwd(), outputPath)}`);
        await runFfmpeg(options.ffmpeg, inputPath, outputPath, options);
        converted += 1;
    }

    console.log(JSON.stringify({ converted, skipped, total: videos.length, outputDir: options.outputDir }, null, 2));
};

await main().catch((error) => {
    console.error(error instanceof Error ? error.message : String(error));
    process.exit(1);
});
