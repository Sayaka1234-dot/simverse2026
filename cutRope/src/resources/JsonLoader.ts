import type {
    JsonCacheEntry,
    LevelJson,
    LoadedLevelEntry,
    MenuStringEntry,
    RawBoxMetadataJson,
} from "@/types/json";

const VITE_ENV = (import.meta as ImportMeta & { env?: { BASE_URL?: string } }).env;

const loadJson = async <T>(url: RequestInfo | URL): Promise<T> => {
    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
    }

    const text = await response.text();
    const contentType = response.headers.get("content-type")?.toLowerCase() ?? "";

    if (contentType && !contentType.includes("json")) {
        throw new Error(`Expected JSON response from ${String(url)}, received ${contentType}`);
    }

    try {
        return JSON.parse(text) as T;
    } catch (error) {
        window.console?.error?.("Failed to parse JSON:", url, error);
        throw error;
    }
};

type ProgressCallback = (loaded: number, total: number) => void;
type LevelManifestJson = string[] | { levels?: string[] };

const normalizeLevelFile = (levelFile: string): string => {
    const trimmed = levelFile.trim();
    return trimmed.endsWith(".json") ? trimmed : `${trimmed}.json`;
};

const normalizeLevelManifest = (manifest: LevelManifestJson): string[] | null => {
    const levels = Array.isArray(manifest) ? manifest : manifest.levels;
    if (!Array.isArray(levels)) {
        return null;
    }

    return levels
        .filter((level): level is string => typeof level === "string" && level.trim().length > 0)
        .map((level) => normalizeLevelFile(level));
};

class JsonLoader {
    private menuJsonLoadComplete = false;

    private loadedJsonFiles = 0;

    private failedJsonFiles = 0;

    private totalJsonFiles = 0;

    private checkCompleteCallback: (() => void) | null = null;

    private progressCallback: ProgressCallback | null = null;

    private readonly jsonCache = new Map<string, JsonCacheEntry | MenuStringEntry[]>();

    getJsonFileCount(): number {
        return this.totalJsonFiles;
    }

    onProgress(callback: ProgressCallback): void {
        this.progressCallback = callback;
    }

    onMenuComplete(callback: () => void): void {
        this.checkCompleteCallback = callback;
    }

    async start(): Promise<void> {
        // Use the configured base from vite config
        const baseUrl = (VITE_ENV?.BASE_URL || "/").replace(/\/$/, "");

        try {
            // First, load the box metadata and menu strings
            const boxMetadataUrl = `${baseUrl}/data/config/editions/net-box-text.json`;
            const menuStringsUrl = `${baseUrl}/data/resources/menu-strings.json`;

            const [boxMetadata, menuStrings] = await Promise.all([
                loadJson<RawBoxMetadataJson[]>(boxMetadataUrl),
                loadJson<MenuStringEntry[]>(menuStringsUrl),
            ]);

            this.jsonCache.set("boxMetadata", boxMetadata);
            this.jsonCache.set("menuStrings", menuStrings);

            let manifestLevelFiles: string[] | null = null;
            try {
                const levelManifestUrl = `${baseUrl}/data/boxes/levels-manifest.json`;
                const manifest = await loadJson<LevelManifestJson>(levelManifestUrl);
                manifestLevelFiles = normalizeLevelManifest(manifest);
            } catch {
                manifestLevelFiles = null;
            }

            const levelFiles: { url: string; key: string; levelId: string }[] = [];

            if (manifestLevelFiles && manifestLevelFiles.length > 0) {
                manifestLevelFiles.forEach((levelFile, index) => {
                    const levelNumber = String(index).padStart(3, "0");
                    levelFiles.push({
                        url: `${baseUrl}/data/boxes/levels/${levelFile}`,
                        key: `level-00-${levelNumber}`,
                        levelId: levelFile.replace(/\.json$/i, ""),
                    });
                });
            } else {
                // Queue level files based on levelCount from metadata for legacy data sets.
                boxMetadata.forEach((box, index) => {
                    if (box.levelCount && typeof box.levelCount === "number") {
                        const boxStr = String(index).padStart(2, "0");
                        for (let level = 1; level <= box.levelCount; level++) {
                            const levelStr = String(level).padStart(2, "0");
                            levelFiles.push({
                                url: `${baseUrl}/data/boxes/levels/${boxStr}-${levelStr}.json`,
                                key: `level-${boxStr}-${levelStr}`,
                                levelId: `${boxStr}-${levelStr}`,
                            });
                        }
                    }
                });
            }

            // Set total to metadata (1) + menu strings (1) + level files
            this.totalJsonFiles = 2 + levelFiles.length;
            this.loadedJsonFiles = 2; // Box metadata and menu strings already loaded

            this.progressCallback?.(this.loadedJsonFiles, this.totalJsonFiles);

            // Load all level JSON files
            const promises = levelFiles.map(async ({ url, key, levelId }) => {
                try {
                    const data = await loadJson<LevelJson>(url);
                    data.levelId = levelId;
                    this.jsonCache.set(key, data);
                    this.loadedJsonFiles++;
                    this.progressCallback?.(this.loadedJsonFiles, this.totalJsonFiles);
                    return { success: true as const, key };
                } catch (error) {
                    // Silent fail for level files that might not exist
                    this.loadedJsonFiles++;
                    this.progressCallback?.(this.loadedJsonFiles, this.totalJsonFiles);
                    return { success: false as const, key, silent: true };
                }
            });

            await Promise.all(promises);
            this.menuJsonLoadComplete = true;
            this.checkCompleteCallback?.();
        } catch (error) {
            this.failedJsonFiles++;
            window.console?.error?.("Failed to load box metadata", error);
            this.menuJsonLoadComplete = true;
            this.checkCompleteCallback?.();
        }
    }

    getJson(key: string): JsonCacheEntry | MenuStringEntry[] | undefined {
        return this.jsonCache.get(key);
    }

    getAllLevels(): Map<string, LoadedLevelEntry[]> {
        const levels = new Map<string, LoadedLevelEntry[]>();
        for (const [key, value] of this.jsonCache.entries()) {
            if (key.startsWith("level-")) {
                const match = key.match(/level-(\d{2})-(\d+)/);
                if (match) {
                    const boxNumber = match[1];
                    const levelNumber = match[2];
                    if (!boxNumber || !levelNumber) {
                        continue;
                    }
                    if (!levels.has(boxNumber)) {
                        levels.set(boxNumber, []);
                    }
                    const levelEntries = levels.get(boxNumber);
                    if (levelEntries) {
                        levelEntries.push({
                            levelNumber,
                            level: value as LevelJson,
                        });
                    }
                }
            }
        }
        return levels;
    }

    getBoxMetadata(): RawBoxMetadataJson[] | undefined {
        const metadata = this.jsonCache.get("boxMetadata");
        if (Array.isArray(metadata)) {
            return metadata as RawBoxMetadataJson[];
        }
        return undefined;
    }

    getMenuStrings(): MenuStringEntry[] | undefined {
        const menuStrings = this.jsonCache.get("menuStrings");
        if (Array.isArray(menuStrings)) {
            return menuStrings as MenuStringEntry[];
        }
        return undefined;
    }
}

// Export a singleton instance
export default new JsonLoader();
