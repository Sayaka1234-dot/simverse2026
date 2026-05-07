import fs from "node:fs/promises";
import path from "node:path";
import { spawn } from "node:child_process";
import process from "node:process";

const getArg = (args, name) => {
    const idx = args.indexOf(`--${name}`);
    if (idx === -1) {
        return null;
    }
    return args[idx + 1] ?? null;
};

const printUsageAndExit = () => {
    console.error(
        "Usage: node scripts/extract-video-frames.mjs --video <path> --out <dir> [--max-frames 8] [--width 960] [--quality 0.85] [--ffmpeg ffmpeg]"
    );
    process.exit(1);
};

const parseNumber = (value, fallback) => {
    const n = Number(value);
    return Number.isFinite(n) && n > 0 ? n : fallback;
};

const probeDurationSeconds = async (ffprobeBin, videoPath) => {
    return await new Promise((resolve, reject) => {
        const child = spawn(
            ffprobeBin,
            ["-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", videoPath],
            { stdio: ["ignore", "pipe", "pipe"] }
        );
        let stdout = "";
        let stderr = "";
        child.stdout.on("data", (chunk) => (stdout += chunk.toString("utf8")));
        child.stderr.on("data", (chunk) => (stderr += chunk.toString("utf8")));
        child.on("error", reject);
        child.on("close", (code) => {
            if (code !== 0) {
                reject(new Error(`ffprobe exited ${code}: ${stderr.trim()}`));
                return;
            }
            const value = Number.parseFloat(stdout.trim());
            if (!Number.isFinite(value) || value <= 0) {
                reject(new Error(`ffprobe returned non-positive duration: ${stdout.trim()}`));
                return;
            }
            resolve(value);
        });
    });
};

const runFfmpeg = async (ffmpegBin, args) => {
    return await new Promise((resolve, reject) => {
        const child = spawn(ffmpegBin, args, { stdio: ["ignore", "ignore", "pipe"] });
        let stderr = "";
        child.stderr.on("data", (chunk) => (stderr += chunk.toString("utf8")));
        child.on("error", reject);
        child.on("close", (code) => {
            if (code !== 0) {
                reject(new Error(`ffmpeg exited ${code}: ${stderr.trim().slice(-500)}`));
                return;
            }
            resolve();
        });
    });
};

const extractFrame = async (ffmpegBin, videoPath, timestampSeconds, outPath, frameWidth, quality) => {
    const qscale = Math.max(2, Math.min(31, Math.round(2 + (1 - quality) * 29)));
    const args = [
        "-y",
        "-ss",
        timestampSeconds.toFixed(3),
        "-i",
        videoPath,
        "-vframes",
        "1",
        "-vf",
        `scale=${frameWidth}:-2:flags=lanczos`,
        "-q:v",
        String(qscale),
        outPath,
    ];
    await runFfmpeg(ffmpegBin, args);
};

const main = async () => {
    const args = process.argv.slice(2);
    const videoPath = getArg(args, "video");
    const outDir = getArg(args, "out");
    if (!videoPath || !outDir) {
        printUsageAndExit();
    }

    const maxFrames = Math.max(1, Math.round(parseNumber(getArg(args, "max-frames"), 8)));
    const frameWidth = Math.max(16, Math.round(parseNumber(getArg(args, "width"), 960)));
    const quality = Math.min(1, Math.max(0, parseNumber(getArg(args, "quality"), 0.85)));
    const ffmpegBin = getArg(args, "ffmpeg") || "ffmpeg";
    const ffprobeBin = getArg(args, "ffprobe") || (ffmpegBin === "ffmpeg" ? "ffprobe" : ffmpegBin.replace(/ffmpeg(\.exe)?$/i, "ffprobe$1"));

    const resolvedVideo = path.resolve(videoPath);
    const resolvedOut = path.resolve(outDir);
    await fs.mkdir(resolvedOut, { recursive: true });

    const duration = await probeDurationSeconds(ffprobeBin, resolvedVideo);

    const framePaths = [];
    for (let i = 0; i < maxFrames; i++) {
        const t = maxFrames === 1 ? duration / 2 : (duration * i) / (maxFrames - 1);
        const safeT = Math.min(Math.max(t, 0), Math.max(duration - 0.05, 0));
        const outPath = path.join(resolvedOut, `frame-${String(i).padStart(2, "0")}.jpg`);
        await extractFrame(ffmpegBin, resolvedVideo, safeT, outPath, frameWidth, quality);
        framePaths.push(outPath);
    }

    process.stdout.write(JSON.stringify({ frames: framePaths }));
};

main().catch((err) => {
    process.stderr.write(`${err && err.stack ? err.stack : String(err)}\n`);
    process.exit(1);
});
