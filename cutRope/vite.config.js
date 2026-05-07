import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs/promises";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";
import process from "node:process";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const APP_VERSION = "7";
const LEVEL_SOLUTION_ENDPOINT = "/__codex/save-level-solution";
const LEVEL_JSON_ENDPOINT = "/__codex/save-level-json";
const LEVEL_ID_PATTERN = /^rope-\d+$/;

const sendJson = (res, statusCode, payload) => {
    res.statusCode = statusCode;
    res.setHeader("Content-Type", "application/json; charset=utf-8");
    res.end(JSON.stringify(payload));
};

const readJsonBody = async (req) => {
    const chunks = [];

    for await (const chunk of req) {
        chunks.push(typeof chunk === "string" ? chunk : String(chunk));
    }

    const raw = chunks.join("").trim();
    if (!raw) {
        return {};
    }

    return JSON.parse(raw);
};

const createLevelSolutionMiddleware = () => {
    const levelsDir = path.resolve(__dirname, "data", "task");
    const levelsDirWithSep = `${levelsDir}${path.sep}`;

    return async (req, res, next) => {
        const requestUrl = req.url || "";
        if (!requestUrl.startsWith(LEVEL_SOLUTION_ENDPOINT)) {
            next();
            return;
        }

        if (req.method !== "POST") {
            sendJson(res, 405, { error: "Method not allowed" });
            return;
        }

        try {
            const body = await readJsonBody(req);
            const levelId = typeof body.levelId === "string" ? body.levelId.trim() : "";
            const commands = typeof body.commands === "string" ? body.commands.trim() : "";
            const stars = typeof body.stars === "number" ? body.stars : Number.NaN;
            const won = body.won === true;

            if (!LEVEL_ID_PATTERN.test(levelId)) {
                sendJson(res, 400, { error: "Invalid levelId. Expected format like rope-000 or rope-271." });
                return;
            }
            if (!commands) {
                sendJson(res, 400, { error: "Commands are required." });
                return;
            }
            if (!won || stars !== 3) {
                sendJson(res, 400, { error: "Only 3-star winning solutions can be submitted." });
                return;
            }

            const levelFile = `${levelId}.json`;
            const levelPath = path.resolve(levelsDir, levelFile);
            if (levelPath !== levelsDir && !levelPath.startsWith(levelsDirWithSep)) {
                sendJson(res, 400, { error: "Resolved level path is outside the levels directory." });
                return;
            }

            const raw = await fs.readFile(levelPath, "utf8");
            const json = JSON.parse(raw);
            const updatedAt = new Date().toISOString();

            json.textCommandSolution = commands;
            json.textCommandSolutionStars = 3;
            json.textCommandSolutionWon = true;
            json.textCommandSolutionUpdatedAt = updatedAt;

            await fs.writeFile(levelPath, `${JSON.stringify(json, null, 4)}\n`, "utf8");
            sendJson(res, 200, {
                ok: true,
                levelId,
                file: levelFile,
                updatedAt,
            });
        } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            sendJson(res, 500, { error: message });
        }
    };
};

const createLevelJsonMiddleware = () => {
    const levelsDir = path.resolve(__dirname, "data", "task");
    const levelsDirWithSep = `${levelsDir}${path.sep}`;

    return async (req, res, next) => {
        const requestUrl = req.url || "";
        if (!requestUrl.startsWith(LEVEL_JSON_ENDPOINT)) {
            next();
            return;
        }

        if (req.method !== "POST") {
            sendJson(res, 405, { error: "Method not allowed" });
            return;
        }

        try {
            const body = await readJsonBody(req);
            const levelId = typeof body.levelId === "string" ? body.levelId.trim() : "";
            const levelJson =
                body.levelJson && typeof body.levelJson === "object" && !Array.isArray(body.levelJson)
                    ? body.levelJson
                    : null;

            if (!LEVEL_ID_PATTERN.test(levelId)) {
                sendJson(res, 400, { error: "Invalid levelId. Expected format like rope-000 or rope-271." });
                return;
            }
            if (!levelJson || !Array.isArray(levelJson.settings) || !Array.isArray(levelJson.objects)) {
                sendJson(res, 400, { error: "levelJson must contain settings[] and objects[]." });
                return;
            }

            const levelFile = `${levelId}.json`;
            const levelPath = path.resolve(levelsDir, levelFile);
            if (levelPath !== levelsDir && !levelPath.startsWith(levelsDirWithSep)) {
                sendJson(res, 400, { error: "Resolved level path is outside the levels directory." });
                return;
            }

            await fs.access(levelPath);

            const updatedAt = new Date().toISOString();
            const updatedJson = {
                ...levelJson,
                levelId,
                levelEditedAt: updatedAt,
            };

            await fs.writeFile(levelPath, `${JSON.stringify(updatedJson, null, 4)}\n`, "utf8");
            sendJson(res, 200, {
                ok: true,
                levelId,
                file: levelFile,
                updatedAt,
                levelJson: updatedJson,
            });
        } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            sendJson(res, 500, { error: message });
        }
    };
};

const levelSavePlugin = () => {
    const solutionMiddleware = createLevelSolutionMiddleware();
    const jsonMiddleware = createLevelJsonMiddleware();

    return {
        name: "ctr-level-save",
        apply: "serve",
        configureServer(server) {
            server.middlewares.use(solutionMiddleware);
            server.middlewares.use(jsonMiddleware);
        },
        configurePreviewServer(server) {
            server.middlewares.use(solutionMiddleware);
            server.middlewares.use(jsonMiddleware);
        },
    };
};

// Bridge legacy /data/boxes/levels{,-manifest}.json URLs to the new
// project-root data/task/ folder, so the browser engine keeps working
// after the data restructure.
const levelDataBridgePlugin = () => {
    const taskDir = path.resolve(__dirname, "data", "task");
    const taskDirWithSep = `${taskDir}${path.sep}`;
    const manifestPath = path.join(taskDir, "manifest.json");

    const bridge = async (req, res, next) => {
        if (req.method && req.method !== "GET" && req.method !== "HEAD") {
            next();
            return;
        }
        const rawUrl = req.url || "";
        const urlPath = rawUrl.split("?")[0].split("#")[0];

        let targetPath = null;
        if (urlPath === "/data/boxes/levels-manifest.json") {
            targetPath = manifestPath;
        } else {
            const match = urlPath.match(/^\/data\/boxes\/levels\/([^/]+\.json)$/);
            if (match) {
                const candidate = path.resolve(taskDir, match[1]);
                if (candidate === taskDir || candidate.startsWith(taskDirWithSep)) {
                    targetPath = candidate;
                }
            }
        }

        if (!targetPath) {
            next();
            return;
        }

        try {
            const body = await fs.readFile(targetPath);
            res.statusCode = 200;
            res.setHeader("Content-Type", "application/json; charset=utf-8");
            res.setHeader("Cache-Control", "no-cache");
            res.end(body);
        } catch (error) {
            if (error && error.code === "ENOENT") {
                res.statusCode = 404;
                res.end();
                return;
            }
            res.statusCode = 500;
            res.end();
        }
    };

    return {
        name: "ctr-level-data-bridge",
        apply: "serve",
        configureServer(server) {
            server.middlewares.use(bridge);
        },
        configurePreviewServer(server) {
            server.middlewares.use(bridge);
        },
    };
};

// Copy data/task/*.json into the build output at dist/data/boxes/levels/
// (and manifest.json -> dist/data/boxes/levels-manifest.json) so the
// production bundle still resolves the legacy URLs that the engine uses.
const levelDataCopyPlugin = () => {
    return {
        name: "ctr-level-data-copy",
        apply: "build",
        async closeBundle() {
            const taskDir = path.resolve(__dirname, "data", "task");
            const outDir = path.resolve(__dirname, "dist", "data", "boxes");
            const outLevelsDir = path.join(outDir, "levels");
            await fs.mkdir(outLevelsDir, { recursive: true });

            const entries = await fs.readdir(taskDir);
            for (const name of entries) {
                const src = path.join(taskDir, name);
                if (name === "manifest.json") {
                    await fs.copyFile(src, path.join(outDir, "levels-manifest.json"));
                } else if (name.endsWith(".json")) {
                    await fs.copyFile(src, path.join(outLevelsDir, name));
                }
            }
        },
    };
};

export default defineConfig(({ mode }) => {
    const isDev = mode === "development";
    const base = process.env.VITE_BASE_NETLIFY || (isDev ? "/" : "/simverse-cutrope");
    const enablePWA = !process.env.VITE_BASE_NETLIFY;

    return {
        base: base,
        // Pin a port distinct from lamp (5174) so both frontends can run in parallel.
        server: { port: 5173, strictPort: true },
        preview: { port: 5173, strictPort: true },
        plugins: [
            levelDataBridgePlugin(),
            levelDataCopyPlugin(),
            levelSavePlugin(),
            enablePWA &&
                VitePWA({
                    registerType: "autoUpdate",
                    includeAssets: ["favicon.ico", "css/ctr.css"],
                    devOptions: {
                        enabled: false,
                    },
                    manifest: {
                        id: "page.yell0wsuit.ctrh5dx",
                        name: "Cut the Rope: H5DX",
                        short_name: "Cut the Rope: H5DX",
                        description:
                            "Play Cut the Rope! A mysterious package has arrived, and the little monster inside has only one request… CANDY!",
                        start_url: `/${base}/`,
                        scope: `/${base}/`,
                        display: "standalone",
                        theme_color: "#000000",
                        background_color: "#000000",
                        icons: [
                            {
                                src: `images/ctr-icon-512.png`,
                                sizes: "512x512",
                                type: "image/png",
                            },
                            {
                                src: `images/ctr-icon.png`,
                                sizes: "2048x2048",
                                type: "image/png",
                            },
                        ],
                    },
                    workbox: {
                        globPatterns: [
                            "**/*.{js,css,html,ico,png,svg,jpg,jpeg,gif,webp,json,woff,woff2,ttf,cur,mp3,ogg}",
                        ],
                        maximumFileSizeToCacheInBytes: 10 * 1024 * 1024, // 10 MB
                        //navigateFallback: `/${base}/index.html`,
                        cleanupOutdatedCaches: true,
                        runtimeCaching: [
                            {
                                urlPattern: ({ url }) => url.pathname.endsWith(".html"),
                                handler: "NetworkFirst",
                                options: {
                                    cacheName: `ctr-html-${APP_VERSION}`,
                                    networkTimeoutSeconds: 3,
                                    expiration: {
                                        maxEntries: 10,
                                        maxAgeSeconds: 60 * 60 * 24 * 7, // 7 days
                                    },
                                    cacheableResponse: {
                                        statuses: [0, 200],
                                    },
                                },
                            },
                            {
                                urlPattern: ({ request }) => request.destination === "script",
                                handler: "StaleWhileRevalidate",
                                options: {
                                    cacheName: `ctr-scripts-${APP_VERSION}`,
                                    expiration: {
                                        maxEntries: 50,
                                        maxAgeSeconds: 60 * 60 * 24 * 7, // 7 days
                                    },
                                    cacheableResponse: {
                                        statuses: [0, 200],
                                    },
                                },
                            },
                            {
                                urlPattern: ({ request, url }) =>
                                    request.destination === "style" ||
                                    url.pathname.includes("/css/"),
                                handler: "StaleWhileRevalidate",
                                options: {
                                    cacheName: `ctr-styles-${APP_VERSION}`,
                                    expiration: {
                                        maxEntries: 20,
                                        maxAgeSeconds: 60 * 60 * 24 * 365, // 365 days
                                    },
                                    cacheableResponse: {
                                        statuses: [0, 200],
                                    },
                                },
                            },
                            {
                                urlPattern: ({ request, url }) =>
                                    request.destination === "image" ||
                                    url.pathname.includes("/images/"),
                                handler: "CacheFirst",
                                options: {
                                    cacheName: `ctr-images-${APP_VERSION}`,
                                    expiration: {
                                        maxEntries: 200,
                                        maxAgeSeconds: 60 * 60 * 24 * 365,
                                    },
                                    cacheableResponse: {
                                        statuses: [0, 200],
                                    },
                                },
                            },
                            {
                                urlPattern: ({ request, url }) =>
                                    request.destination === "font" ||
                                    url.pathname.includes("/fonts/"),
                                handler: "CacheFirst",
                                options: {
                                    cacheName: `ctr-fonts-${APP_VERSION}`,
                                    expiration: {
                                        maxAgeSeconds: 60 * 60 * 24 * 365,
                                    },
                                    cacheableResponse: {
                                        statuses: [0, 200],
                                    },
                                },
                            },
                            {
                                urlPattern: ({ request, url }) =>
                                    request.destination === "audio" ||
                                    url.pathname.includes("/audio/"),
                                handler: "CacheFirst",
                                options: {
                                    cacheName: `ctr-audio-${APP_VERSION}`,
                                    expiration: {
                                        maxAgeSeconds: 60 * 60 * 24 * 365,
                                    },
                                    cacheableResponse: {
                                        statuses: [0, 200],
                                    },
                                },
                            },
                            {
                                urlPattern: ({ url }) =>
                                    url.pathname.endsWith(".json") &&
                                    url.pathname.includes("/data/"),
                                handler: "NetworkFirst",
                                options: {
                                    cacheName: `ctr-json-${APP_VERSION}`,
                                    networkTimeoutSeconds: 3,
                                    expiration: {
                                        maxAgeSeconds: 60 * 60 * 24 * 365,
                                    },
                                    cacheableResponse: {
                                        statuses: [0, 200],
                                    },
                                },
                            },
                        ],
                    },
                }),
        ],
        resolve: {
            alias: {
                "@": path.resolve(__dirname, "./src"),
            },
        },
        build: {
            rollupOptions: {
                output: {
                    advancedChunks: {
                        groups: [
                            {
                                name(moduleId) {
                                    const idx = moduleId.indexOf("/src/");
                                    if (idx >= 0) {
                                        let srcPath = moduleId.slice(idx + 5); // after '/src/'
                                        srcPath = srcPath.replace(/\.(js|ts|jsx|tsx)$/, "");
                                        srcPath = srcPath.replace(/\\/g, "/");
                                        return srcPath;
                                    }
                                    return null;
                                },
                                test: /[\\/]src[\\/]/,
                                priority: 50,
                            },
                        ],
                    },
                },
            },
        },
    };
});
