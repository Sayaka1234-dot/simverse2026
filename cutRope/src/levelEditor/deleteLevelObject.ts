import type { LevelEntity, LevelJson } from "@/types/json";

const PROTECTED_LEVEL_OBJECT_NAMES = new Set([2, 50, 51, 52]);

export type DeleteLevelObjectResult =
    | {
          deleted: true;
          object: LevelEntity;
          objectIndex: number;
      }
    | {
          deleted: false;
          reason: "missing" | "protected";
      };

export function canDeleteLevelObject(object: LevelEntity | null | undefined): boolean {
    if (!object) {
        return false;
    }
    return !PROTECTED_LEVEL_OBJECT_NAMES.has(Number(object.name));
}

export function deleteLevelObjectAt(level: LevelJson, objectIndex: number): DeleteLevelObjectResult {
    const object = level.objects[objectIndex];
    if (!object) {
        return { deleted: false, reason: "missing" };
    }

    if (!canDeleteLevelObject(object)) {
        return { deleted: false, reason: "protected" };
    }

    level.objects.splice(objectIndex, 1);
    return {
        deleted: true,
        object,
        objectIndex,
    };
}
