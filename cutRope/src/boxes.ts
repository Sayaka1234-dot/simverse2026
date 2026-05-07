import JsonLoader from "@/resources/JsonLoader";
import type { LevelJson, LoadedLevelEntry } from "@/types/json";

// Cached boxes data
let cachedBoxes: { levels: LevelJson[] }[] | null = null;

// Get levels from JsonLoader which loads them at runtime from public folder
/**
 * Resolve and memoize level JSON grouped by box.
 * @returns {Array<{ levels: LevelJson[] }>}
 */
const getLevels = (): { levels: LevelJson[] }[] => {
    if (cachedBoxes) {
        return cachedBoxes;
    }

    const groupedLevels: [string, LoadedLevelEntry[]][] = Array.from(JsonLoader.getAllLevels());

    if (groupedLevels.length === 0) {
        // Return empty array if data not loaded yet
        return [];
    }

    const toNumericIndex = (value: string): number => {
        const parsed = Number.parseInt(value, 10);
        return Number.isFinite(parsed) ? parsed : 0;
    };

    const flattenedLevels = groupedLevels
        .sort(([boxA], [boxB]) => toNumericIndex(boxA) - toNumericIndex(boxB))
        .flatMap(([boxNumber, levels]) =>
            levels
                .sort(
                    (levelA, levelB) =>
                        toNumericIndex(levelA.levelNumber) - toNumericIndex(levelB.levelNumber)
                )
                .map(({ levelNumber, level }) => {
                    const levelId =
                        typeof level.levelId === "string" && level.levelId.length > 0
                            ? level.levelId
                            : `${boxNumber}-${levelNumber}`;
                    (level as Record<string, unknown>).levelId = levelId;
                    return level;
                })
        );

    cachedBoxes = [{ levels: flattenedLevels }];

    return cachedBoxes;
};

// Export a Proxy that returns the boxes loaded from JSON
// This ensures the data is available when accessed, even if loaded async
export default new Proxy([] as { levels: LevelJson[] }[], {
    get(target, prop) {
        const boxes = getLevels();
        return Reflect.get(boxes, prop);
    },
    has(target, prop) {
        const boxes = getLevels();
        return prop in boxes;
    },
    ownKeys() {
        const boxes = getLevels();
        return Reflect.ownKeys(boxes);
    },
    getOwnPropertyDescriptor(target, prop) {
        const boxes = getLevels();
        return Reflect.getOwnPropertyDescriptor(boxes, prop);
    },
});
