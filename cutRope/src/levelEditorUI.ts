import ctrRootController from "@/game/CTRRootController";
import GameView from "@/game/GameView";
import LevelState from "@/game/LevelState";
import edition from "@/config/editions/net-edition";
import { canDeleteLevelObject, deleteLevelObjectAt } from "@/levelEditor/deleteLevelObject";
import type GameScene from "@/GameScene";
import type GameController from "@/game/GameController";
import type { LevelEntity, LevelJson } from "@/types/json";

type EditableKind =
    | "target"
    | "star"
    | "rope"
    | "candy"
    | "candy_left"
    | "candy_right"
    | "gravity"
    | "lantern"
    | "lightbulb"
    | "object";

type AddableKind =
    | "target"
    | "star"
    | "candy"
    | "candy_left"
    | "candy_right"
    | "rope_soft"
    | "rope_hard"
    | "gravity"
    | "lantern"
    | "lightbulb";

type RopeTension = "soft" | "hard";

interface EditableHandle {
    objectIndex: number;
    runtimeIndex: number;
    kind: EditableKind;
    label: string;
    x: number;
    y: number;
}

const SAVE_ENDPOINT = "/__codex/save-level-json";
const DEFAULT_LEVEL_WIDTH = 320;
const DEFAULT_LEVEL_HEIGHT = 480;
const HANDLE_PICK_RADIUS = 24;

const toggleBtn = document.getElementById("levelEditorToggle") as HTMLButtonElement | null;
const saveBtn = document.getElementById("levelEditorSave") as HTMLButtonElement | null;
const cancelBtn = document.getElementById("levelEditorCancel") as HTMLButtonElement | null;
const addKindSelect = document.getElementById("levelEditorAddKind") as HTMLSelectElement | null;
const addBtn = document.getElementById("levelEditorAdd") as HTMLButtonElement | null;
const deleteBtn = document.getElementById("levelEditorDelete") as HTMLButtonElement | null;
const ropeControls = document.getElementById("levelEditorRopeControls") as HTMLDivElement | null;
const ropeTensionSelect = document.getElementById("levelEditorRopeTension") as HTMLSelectElement | null;
const ropeLengthInput = document.getElementById("levelEditorRopeLength") as HTMLInputElement | null;
const applyRopeBtn = document.getElementById("levelEditorApplyRope") as HTMLButtonElement | null;
const hintDiv = document.getElementById("levelEditorHint") as HTMLDivElement | null;
const gameCanvas = document.getElementById("c") as HTMLCanvasElement | null;
const gameArea = document.getElementById("gameArea") as HTMLElement | null;
const levelMenu = document.getElementById("levelMenu") as HTMLElement | null;

const overlay = document.createElement("canvas");
const overlayCtx = overlay.getContext("2d");
overlay.id = "levelEditorOverlay";
overlay.style.position = gameArea ? "absolute" : "fixed";
overlay.style.left = "0";
overlay.style.top = "0";
overlay.style.zIndex = "500";
overlay.style.display = "none";
overlay.style.pointerEvents = "none";
overlay.style.touchAction = "none";
overlay.style.cursor = "grab";
(gameArea ?? document.body).appendChild(overlay);

let isEditing = false;
let isSaving = false;
let originalLevel: LevelJson | null = null;
let draftLevel: LevelJson | null = null;
let selectedHandle: EditableHandle | null = null;
let draggingPointerId: number | null = null;

function cloneLevel(level: LevelJson): LevelJson {
    return JSON.parse(JSON.stringify(level)) as LevelJson;
}

function setHint(message: string): void {
    if (hintDiv) {
        hintDiv.textContent = message;
    }
}

function setButtonEnabled(button: HTMLButtonElement | null, enabled: boolean): void {
    if (!button) {
        return;
    }
    button.disabled = !enabled;
    button.style.opacity = enabled ? "1" : "0.45";
    button.style.cursor = enabled ? "pointer" : "not-allowed";
}

function updateButtons(): void {
    if (toggleBtn) {
        toggleBtn.textContent = isEditing ? "Exit Edit Mode" : "Edit Current Level";
        toggleBtn.style.background = isEditing
            ? "linear-gradient(135deg, #e67e22, #ca6f1e)"
            : "linear-gradient(135deg, #3498db, #2471a3)";
    }
    setButtonEnabled(saveBtn, isEditing && !isSaving);
    setButtonEnabled(cancelBtn, isEditing && !isSaving);
    setButtonEnabled(addBtn, isEditing && !isSaving);
    setButtonEnabled(deleteBtn, isEditing && !isSaving && canDeleteLevelObject(getSelectedObject()));
    if (addKindSelect) {
        addKindSelect.disabled = !isEditing || isSaving;
        addKindSelect.style.opacity = isEditing && !isSaving ? "1" : "0.45";
        addKindSelect.style.cursor = isEditing && !isSaving ? "pointer" : "not-allowed";
    }
    if (saveBtn) {
        saveBtn.textContent = isSaving ? "Saving..." : "Save JSON";
    }
    updateRopeControls();
}

function getSelectedObject(): LevelEntity | undefined {
    if (!draftLevel || !selectedHandle) {
        return undefined;
    }
    return draftLevel.objects[selectedHandle.objectIndex];
}

function getGameScene(): GameScene | null {
    try {
        const gameCtrl = ctrRootController.getChild(3) as GameController | null | undefined;
        if (!gameCtrl) {
            return null;
        }
        const view = gameCtrl.getView(0);
        if (!view) {
            return null;
        }
        return (view.getChild(GameView.ElementType.GAME_SCENE) as GameScene | undefined) ?? null;
    } catch {
        return null;
    }
}

function getCurrentLevelId(): string | null {
    const level = LevelState.loadedMap;
    if (!level || typeof level.levelId !== "string" || !level.levelId.trim()) {
        return null;
    }
    return level.levelId.trim();
}

function updateLevelCache(level: LevelJson): void {
    LevelState.loadedMap = level;
    const box = edition.boxes[LevelState.pack];
    if (box?.levels) {
        box.levels[LevelState.level] = level;
    }
}

function getMapSize(level: LevelJson): { width: number; height: number } {
    const mapSettings = level.settings.find((item) => Number(item.name) === 0);
    const width = typeof mapSettings?.width === "number" ? mapSettings.width : DEFAULT_LEVEL_WIDTH;
    const height =
        typeof mapSettings?.height === "number" ? mapSettings.height : DEFAULT_LEVEL_HEIGHT;
    return { width, height };
}

function isNumber(value: unknown): value is number {
    return typeof value === "number" && Number.isFinite(value);
}

function clamp(value: number, min: number, max: number): number {
    return Math.max(min, Math.min(max, value));
}

function getGameDesign(level: LevelJson): LevelEntity | null {
    return level.settings.find((item) => Number(item.name) === 1) ?? null;
}

function ensureTwoParts(level: LevelJson): void {
    const design = getGameDesign(level);
    if (design) {
        design.twoParts = true;
    }
}

function firstObjectIndexByName(level: LevelJson, name: number): number {
    return level.objects.findIndex((object) => Number(object.name) === name);
}

function getObjectPoint(object: LevelEntity | undefined): { x: number; y: number } | null {
    if (!object || !isNumber(object.x) || !isNumber(object.y)) {
        return null;
    }
    return { x: object.x, y: object.y };
}

function getRopeTailObject(level: LevelJson, rope: LevelEntity | null | undefined): LevelEntity | undefined {
    const twoParts = Boolean(getGameDesign(level)?.twoParts);
    if (twoParts) {
        const part = rope?.part === "R" ? 51 : 50;
        return level.objects.find((object) => Number(object.name) === part) ??
            level.objects.find((object) => Number(object.name) === 52);
    }
    return level.objects.find((object) => Number(object.name) === 52);
}

function computeRopeDistance(level: LevelJson, rope: LevelEntity): number | null {
    const anchor = getObjectPoint(rope);
    const tail = getObjectPoint(getRopeTailObject(level, rope));
    if (!anchor || !tail) {
        return null;
    }
    return Math.hypot(anchor.x - tail.x, anchor.y - tail.y);
}

function computeRopeLength(level: LevelJson, rope: LevelEntity, tension: RopeTension): number {
    const distance = computeRopeDistance(level, rope);
    if (!distance) {
        return tension === "hard" ? 65 : 110;
    }
    const multiplier = tension === "hard" ? 0.72 : 1.28;
    return Math.round(clamp(distance * multiplier, 20, 600));
}

function inferRopeTension(level: LevelJson, rope: LevelEntity): RopeTension {
    const distance = computeRopeDistance(level, rope);
    const length = isNumber(rope.length) ? rope.length : null;
    if (!distance || length == null) {
        return "soft";
    }
    return length < distance ? "hard" : "soft";
}

function getCanvasCenterLevelPosition(level: LevelJson): { x: number; y: number } {
    const mapSize = getMapSize(level);
    const scene = getGameScene();
    if (!scene || overlay.width <= 0 || overlay.height <= 0) {
        return {
            x: Math.round(mapSize.width / 2),
            y: Math.round(mapSize.height / 2),
        };
    }

    const center = canvasToLevel(overlay.width / 2, overlay.height / 2, scene);
    return {
        x: Math.round(clamp(center.x, 0, mapSize.width)),
        y: Math.round(clamp(center.y, 0, mapSize.height)),
    };
}

function createLevelObject(kind: AddableKind, x: number, y: number, level: LevelJson): LevelEntity {
    switch (kind) {
        case "target":
            return { name: 2, x, y };
        case "star":
            return { name: 3, x, y, timeout: -1 };
        case "candy":
            return { name: 52, x, y };
        case "candy_left":
            ensureTwoParts(level);
            return { name: 50, x, y };
        case "candy_right":
            ensureTwoParts(level);
            return { name: 51, x, y };
        case "gravity":
            return { name: 53, x, y };
        case "lantern":
            return { name: 132, x, y, candyCaptured: false };
        case "lightbulb":
            return { name: 134, x, y, litRadius: 50 };
        case "rope_hard":
        case "rope_soft": {
            const rope: LevelEntity = {
                name: 100,
                x,
                y,
                length: 90,
                wheel: false,
                gun: false,
                radius: -1,
                moveLength: -1,
                moveVertical: false,
                moveOffset: 0,
                spider: false,
                part: "L",
            };
            rope.length = computeRopeLength(level, rope, kind === "rope_hard" ? "hard" : "soft");
            return rope;
        }
    }
}

function resolveKind(name: LevelEntity["name"]): EditableKind | null {
    switch (Number(name)) {
        case 2:
            return "target";
        case 3:
            return "star";
        case 50:
            return "candy_left";
        case 51:
            return "candy_right";
        case 52:
            return "candy";
        case 53:
            return "gravity";
        case 100:
            return "rope";
        case 132:
            return "lantern";
        case 134:
            return "lightbulb";
        default:
            return null;
    }
}

function labelFor(kind: EditableKind, runtimeIndex: number, objectName: LevelEntity["name"]): string {
    switch (kind) {
        case "target":
            return `M${runtimeIndex}`;
        case "star":
            return `S${runtimeIndex}`;
        case "rope":
            return `R${runtimeIndex}`;
        case "candy":
            return `C${runtimeIndex}`;
        case "candy_left":
            return `CL${runtimeIndex}`;
        case "candy_right":
            return `CR${runtimeIndex}`;
        case "gravity":
            return `G${runtimeIndex}`;
        case "lantern":
            return `L${runtimeIndex}`;
        case "lightbulb":
            return `LB${runtimeIndex}`;
        default:
            return `O${String(objectName)}.${runtimeIndex}`;
    }
}

function buildHandles(level: LevelJson): EditableHandle[] {
    const counts = new Map<string, number>();

    return level.objects.flatMap((object, objectIndex) => {
        if (!isNumber(object.x) || !isNumber(object.y)) {
            return [];
        }

        const knownKind = resolveKind(object.name);
        const kind: EditableKind = knownKind ?? "object";
        const key = String(object.name);
        const runtimeIndex = counts.get(key) ?? 0;
        counts.set(key, runtimeIndex + 1);

        return [
            {
                objectIndex,
                runtimeIndex,
                kind,
                label: labelFor(kind, runtimeIndex, object.name),
                x: object.x,
                y: object.y,
            },
        ];
    });
}

function syncOverlayRect(): void {
    if (!gameCanvas) {
        return;
    }
    overlay.width = gameCanvas.width;
    overlay.height = gameCanvas.height;

    if (overlay.parentElement === gameArea) {
        overlay.style.left = `${gameCanvas.offsetLeft}px`;
        overlay.style.top = `${gameCanvas.offsetTop}px`;
        overlay.style.width = `${gameCanvas.width}px`;
        overlay.style.height = `${gameCanvas.height}px`;
        return;
    }

    const rect = gameCanvas.getBoundingClientRect();
    overlay.style.left = `${rect.left}px`;
    overlay.style.top = `${rect.top}px`;
    overlay.style.width = `${rect.width}px`;
    overlay.style.height = `${rect.height}px`;
}

function levelToCanvas(x: number, y: number, scene: GameScene): { x: number; y: number } {
    return {
        x: x * scene.PM + scene.PMX - scene.camera.pos.x,
        y: y * scene.PM + scene.PMY - scene.camera.pos.y,
    };
}

function canvasToLevel(x: number, y: number, scene: GameScene): { x: number; y: number } {
    return {
        x: (x + scene.camera.pos.x - scene.PMX) / scene.PM,
        y: (y + scene.camera.pos.y - scene.PMY) / scene.PM,
    };
}

function pointerToCanvas(event: PointerEvent): { x: number; y: number } | null {
    if (!gameCanvas) {
        return null;
    }
    const rect = gameCanvas.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) {
        return null;
    }
    return {
        x: ((event.clientX - rect.left) * gameCanvas.width) / rect.width,
        y: ((event.clientY - rect.top) * gameCanvas.height) / rect.height,
    };
}

function colorFor(kind: EditableKind): string {
    switch (kind) {
        case "target":
            return "rgba(48, 214, 128, 0.86)";
        case "star":
            return "rgba(255, 220, 64, 0.9)";
        case "rope":
            return "rgba(90, 190, 255, 0.88)";
        case "candy":
        case "candy_left":
        case "candy_right":
            return "rgba(255, 112, 112, 0.88)";
        case "gravity":
            return "rgba(176, 130, 255, 0.88)";
        case "lantern":
            return "rgba(255, 150, 70, 0.9)";
        case "lightbulb":
            return "rgba(255, 245, 160, 0.9)";
        default:
            return "rgba(230, 230, 230, 0.75)";
    }
}

function drawOverlay(): void {
    if (!overlayCtx || !draftLevel || !isEditing) {
        return;
    }

    const scene = getGameScene();
    overlayCtx.clearRect(0, 0, overlay.width, overlay.height);
    if (!scene) {
        return;
    }

    const handles = buildHandles(draftLevel);
    overlayCtx.save();
    overlayCtx.font = "bold 15px Consolas, monospace";
    overlayCtx.textBaseline = "middle";
    overlayCtx.lineWidth = 2;

    for (const handle of handles) {
        const pos = levelToCanvas(handle.x, handle.y, scene);
        const selected =
            selectedHandle?.objectIndex === handle.objectIndex &&
            selectedHandle.runtimeIndex === handle.runtimeIndex;
        const radius = selected ? 12 : 9;

        overlayCtx.beginPath();
        overlayCtx.arc(pos.x, pos.y, radius, 0, Math.PI * 2);
        overlayCtx.fillStyle = colorFor(handle.kind);
        overlayCtx.fill();
        overlayCtx.strokeStyle = selected ? "#ffffff" : "rgba(255,255,255,0.78)";
        overlayCtx.stroke();

        overlayCtx.fillStyle = "rgba(0, 0, 0, 0.68)";
        const textWidth = overlayCtx.measureText(handle.label).width;
        overlayCtx.fillRect(pos.x - textWidth / 2 - 5, pos.y - 28, textWidth + 10, 18);
        overlayCtx.fillStyle = "#ffffff";
        overlayCtx.textAlign = "center";
        overlayCtx.fillText(handle.label, pos.x, pos.y - 19);

        if (selected) {
            overlayCtx.strokeStyle = "rgba(255,255,255,0.65)";
            overlayCtx.beginPath();
            overlayCtx.moveTo(pos.x - 18, pos.y);
            overlayCtx.lineTo(pos.x + 18, pos.y);
            overlayCtx.moveTo(pos.x, pos.y - 18);
            overlayCtx.lineTo(pos.x, pos.y + 18);
            overlayCtx.stroke();
        }
    }

    overlayCtx.restore();
}

function updateRopeControls(): void {
    if (!ropeControls || !ropeTensionSelect || !ropeLengthInput || !draftLevel) {
        if (ropeControls) {
            ropeControls.style.display = "none";
        }
        return;
    }

    const object = selectedHandle ? draftLevel.objects[selectedHandle.objectIndex] : undefined;
    if (!isEditing || !object || selectedHandle?.kind !== "rope") {
        ropeControls.style.display = "none";
        return;
    }

    ropeControls.style.display = "grid";
    ropeTensionSelect.value = inferRopeTension(draftLevel, object);
    ropeLengthInput.value = String(isNumber(object.length) ? object.length : computeRopeLength(draftLevel, object, "soft"));
}

function freezeSceneForEdit(): void {
    const scene = getGameScene();
    if (!scene || !isEditing) {
        return;
    }
    scene.touchable = false;
    scene.updateable = false;
}

function setPointPosition(point: unknown, x: number, y: number): void {
    const maybePoint = point as
        | {
              pos?: { x: number; y: number; copyFrom?: (value: { x: number; y: number }) => void };
              prevPos?: { x: number; y: number; copyFrom?: (value: { x: number; y: number }) => void };
              pin?: { x: number; y: number; copyFrom?: (value: { x: number; y: number }) => void };
          }
        | null
        | undefined;
    if (!maybePoint?.pos) {
        return;
    }

    maybePoint.pos.x = x;
    maybePoint.pos.y = y;
    if (maybePoint.prevPos) {
        maybePoint.prevPos.x = x;
        maybePoint.prevPos.y = y;
    }
    if (maybePoint.pin) {
        maybePoint.pin.x = x;
        maybePoint.pin.y = y;
    }
}

function updateRuntimeObject(handle: EditableHandle, scene: GameScene): void {
    const object = draftLevel?.objects[handle.objectIndex];
    if (!object || !isNumber(object.x) || !isNumber(object.y)) {
        return;
    }

    const worldX = object.x * scene.PM + scene.PMX;
    const worldY = object.y * scene.PM + scene.PMY;
    const sceneAny = scene as GameScene & Record<string, any>;

    switch (handle.kind) {
        case "target":
            scene.target.x = worldX;
            scene.target.y = worldY;
            if (sceneAny.support) {
                sceneAny.support.x = worldX;
                sceneAny.support.y = worldY;
            }
            break;
        case "star": {
            const star = scene.stars[handle.runtimeIndex];
            if (star) {
                star.x = worldX;
                star.y = worldY;
            }
            break;
        }
        case "rope": {
            const grab = scene.bungees[handle.runtimeIndex];
            if (!grab) {
                break;
            }
            grab.x = worldX;
            grab.y = worldY;
            if (grab.rope) {
                setPointPosition(grab.rope.bungeeAnchor, worldX, worldY);
            }
            break;
        }
        case "candy":
            setPointPosition(scene.star, worldX, worldY);
            scene.candy.x = worldX;
            scene.candy.y = worldY;
            break;
        case "candy_left":
            setPointPosition(scene.starL, worldX, worldY);
            if (sceneAny.candyL) {
                sceneAny.candyL.x = worldX;
                sceneAny.candyL.y = worldY;
            }
            break;
        case "candy_right":
            setPointPosition(scene.starR, worldX, worldY);
            if (sceneAny.candyR) {
                sceneAny.candyR.x = worldX;
                sceneAny.candyR.y = worldY;
            }
            break;
        case "gravity":
            if (scene.gravityButton) {
                scene.gravityButton.x = worldX;
                scene.gravityButton.y = worldY;
            }
            break;
        case "lantern": {
            const lantern = scene.lanterns[handle.runtimeIndex];
            if (lantern) {
                lantern.x = worldX;
                lantern.y = worldY;
            }
            break;
        }
        case "lightbulb": {
            const bulb = scene.lightbulbs[handle.runtimeIndex];
            if (bulb) {
                const bulbAny = bulb as unknown as {
                    x?: number;
                    y?: number;
                    constraint?: {
                        pos?: { x: number; y: number };
                        prevPos?: { x: number; y: number };
                    };
                };
                bulbAny.x = worldX;
                bulbAny.y = worldY;
                if (bulbAny.constraint?.pos) {
                    bulbAny.constraint.pos.x = worldX;
                    bulbAny.constraint.pos.y = worldY;
                }
                if (bulbAny.constraint?.prevPos) {
                    bulbAny.constraint.prevPos.x = worldX;
                    bulbAny.constraint.prevPos.y = worldY;
                }
            }
            break;
        }
        default:
            break;
    }
}

function findNearestHandle(canvasX: number, canvasY: number): EditableHandle | null {
    if (!draftLevel) {
        return null;
    }
    const scene = getGameScene();
    if (!scene) {
        return null;
    }

    let nearest: EditableHandle | null = null;
    let nearestDistance = Number.POSITIVE_INFINITY;
    for (const handle of buildHandles(draftLevel)) {
        const pos = levelToCanvas(handle.x, handle.y, scene);
        const distance = Math.hypot(canvasX - pos.x, canvasY - pos.y);
        if (distance < nearestDistance) {
            nearestDistance = distance;
            nearest = handle;
        }
    }

    return nearestDistance <= HANDLE_PICK_RADIUS ? nearest : null;
}

function moveSelectedHandle(canvasX: number, canvasY: number): void {
    if (!draftLevel || !selectedHandle) {
        return;
    }
    const scene = getGameScene();
    if (!scene) {
        return;
    }

    const object = draftLevel.objects[selectedHandle.objectIndex];
    if (!object) {
        return;
    }

    const mapSize = getMapSize(draftLevel);
    const levelPos = canvasToLevel(canvasX, canvasY, scene);
    object.x = Math.round(clamp(levelPos.x, 0, mapSize.width));
    object.y = Math.round(clamp(levelPos.y, 0, mapSize.height));
    selectedHandle.x = object.x;
    selectedHandle.y = object.y;

    updateRuntimeObject(selectedHandle, scene);
    drawOverlay();
    updateRopeControls();
    setHint(`Editing ${selectedHandle.label}: x=${object.x}, y=${object.y}. Click Save JSON when ready.`);
}

function enableOverlay(): void {
    syncOverlayRect();
    overlay.style.display = "block";
    overlay.style.pointerEvents = "auto";
}

function disableOverlay(): void {
    overlay.style.display = "none";
    overlay.style.pointerEvents = "none";
    selectedHandle = null;
    draggingPointerId = null;
    updateButtons();
}

function closePauseMenu(): void {
    if (levelMenu) {
        levelMenu.style.display = "none";
    }
    ctrRootController.resumeLevel();
}

function restartWithLevel(level: LevelJson): void {
    closePauseMenu();
    updateLevelCache(level);
    ctrRootController.restartLevel();
    closePauseMenu();
}

function startEditing(): void {
    const level = LevelState.loadedMap;
    const levelId = getCurrentLevelId();
    if (!level || !levelId) {
        setHint("Open a level before using the editor.");
        return;
    }

    originalLevel = cloneLevel(level);
    draftLevel = cloneLevel(level);
    isEditing = true;
    restartWithLevel(draftLevel);
    enableOverlay();
    freezeSceneForEdit();
    updateButtons();
    setHint(`Edit mode for ${levelId}. Drag M/S/R/C/G handles, then save or cancel.`);
    requestAnimationFrame(() => {
        freezeSceneForEdit();
        drawOverlay();
    });
}

function stopEditing(): void {
    isEditing = false;
    isSaving = false;
    disableOverlay();
    updateButtons();
}

async function saveEditing(): Promise<void> {
    if (!draftLevel || isSaving) {
        return;
    }
    const levelId = getCurrentLevelId();
    if (!levelId) {
        setHint("Cannot save: current level has no levelId.");
        return;
    }

    isSaving = true;
    updateButtons();
    setHint(`Saving ${levelId}.json ...`);

    try {
        const response = await fetch(SAVE_ENDPOINT, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                levelId,
                levelJson: draftLevel,
            }),
        });
        const result = (await response.json().catch(() => null)) as
            | {
                  error?: string;
                  levelJson?: LevelJson;
              }
            | null;

        if (!response.ok || !result?.levelJson) {
            throw new Error(result?.error || `Save request failed with status ${response.status}`);
        }

        const savedLevel = result.levelJson;
        stopEditing();
        restartWithLevel(savedLevel);
        setHint(`Saved ${levelId}.json and reloaded the level.`);
    } catch (error) {
        isSaving = false;
        updateButtons();
        freezeSceneForEdit();
        const message = error instanceof Error ? error.message : String(error);
        setHint(`Save failed: ${message}`);
    }
}

function cancelEditing(): void {
    if (!originalLevel) {
        stopEditing();
        setHint("Edit mode cancelled.");
        return;
    }

    const levelId = getCurrentLevelId();
    const restored = cloneLevel(originalLevel);
    stopEditing();
    restartWithLevel(restored);
    setHint(levelId ? `Cancelled edits and reloaded ${levelId}.` : "Cancelled edits.");
}

function refreezeAfterRestart(selectedObjectIndex?: number): void {
    enableOverlay();
    freezeSceneForEdit();
    if (selectedObjectIndex !== undefined && draftLevel) {
        selectedHandle =
            buildHandles(draftLevel).find((handle) => handle.objectIndex === selectedObjectIndex) ?? null;
    } else {
        selectedHandle = null;
    }
    updateButtons();
    drawOverlay();
    requestAnimationFrame(() => {
        freezeSceneForEdit();
        updateButtons();
        drawOverlay();
    });
}

function selectExistingObject(objectIndex: number): void {
    if (!draftLevel) {
        return;
    }
    selectedHandle = buildHandles(draftLevel).find((handle) => handle.objectIndex === objectIndex) ?? null;
    updateButtons();
    drawOverlay();
}

function addSelectedTool(): void {
    if (!isEditing || !draftLevel || isSaving) {
        return;
    }

    const kind = (addKindSelect?.value ?? "star") as AddableKind;
    const singletonNameByKind: Partial<Record<AddableKind, number>> = {
        target: 2,
        candy: 52,
        candy_left: 50,
        candy_right: 51,
        gravity: 53,
    };
    const singletonName = singletonNameByKind[kind];
    if (singletonName !== undefined) {
        const existingIndex = firstObjectIndexByName(draftLevel, singletonName);
        if (existingIndex >= 0) {
            selectExistingObject(existingIndex);
            setHint("This level already has that singleton tool. I selected it so you can move it.");
            return;
        }
    }

    const pos = getCanvasCenterLevelPosition(draftLevel);
    const object = createLevelObject(kind, pos.x, pos.y, draftLevel);
    const objectIndex = draftLevel.objects.length;
    draftLevel.objects.push(object);
    restartWithLevel(draftLevel);
    refreezeAfterRestart(objectIndex);
    setHint(`Added ${labelFor(resolveKind(object.name) ?? "object", 0, object.name)} at x=${pos.x}, y=${pos.y}. Drag it, then save.`);
}

function deleteSelectedTool(): void {
    if (!isEditing || !draftLevel || !selectedHandle || isSaving) {
        return;
    }

    const label = selectedHandle.label;
    const result = deleteLevelObjectAt(draftLevel, selectedHandle.objectIndex);
    if (!result.deleted) {
        const message = result.reason === "protected"
            ? `${label} is protected. Monster and candy objects cannot be deleted in this version.`
            : "The selected object no longer exists.";
        setHint(message);
        updateButtons();
        drawOverlay();
        return;
    }

    restartWithLevel(draftLevel);
    refreezeAfterRestart();
    setHint(`Deleted ${label}. Click Save JSON to keep the change, or Cancel to restore the level.`);
}

function applySelectedRopeSettings(): void {
    if (!isEditing || !draftLevel || !selectedHandle || selectedHandle.kind !== "rope") {
        setHint("Select a rope handle first, then apply rope settings.");
        return;
    }

    const rope = draftLevel.objects[selectedHandle.objectIndex];
    if (!rope) {
        return;
    }

    const tension = (ropeTensionSelect?.value === "hard" ? "hard" : "soft") as RopeTension;
    const typedLength = Number(ropeLengthInput?.value);
    rope.length = Number.isFinite(typedLength) && typedLength > 0
        ? Math.round(clamp(typedLength, 10, 600))
        : computeRopeLength(draftLevel, rope, tension);
    if (ropeTensionSelect && ropeLengthInput) {
        ropeTensionSelect.value = tension;
        ropeLengthInput.value = String(rope.length);
    }

    const objectIndex = selectedHandle.objectIndex;
    restartWithLevel(draftLevel);
    refreezeAfterRestart(objectIndex);
    setHint(`Updated rope ${selectedHandle.label}: length=${rope.length}, type=${tension === "hard" ? "hard/taut" : "soft"}.`);
}

function previewSelectedRopeTension(): void {
    if (!draftLevel || !selectedHandle || selectedHandle.kind !== "rope") {
        return;
    }
    const rope = draftLevel.objects[selectedHandle.objectIndex];
    if (!rope || !ropeLengthInput) {
        return;
    }
    const tension = ropeTensionSelect?.value === "hard" ? "hard" : "soft";
    ropeLengthInput.value = String(computeRopeLength(draftLevel, rope, tension));
}

function stopPanelPointerEvent(event: Event): void {
    event.stopPropagation();
}

[
    toggleBtn,
    saveBtn,
    cancelBtn,
    addBtn,
    deleteBtn,
    applyRopeBtn,
    addKindSelect,
    ropeTensionSelect,
    ropeLengthInput,
].forEach((button) => {
    button?.addEventListener("pointerdown", stopPanelPointerEvent);
    button?.addEventListener("mousedown", stopPanelPointerEvent);
    button?.addEventListener("touchstart", stopPanelPointerEvent);
});

overlay.addEventListener("pointerdown", (event) => {
    if (!isEditing) {
        return;
    }
    event.preventDefault();
    event.stopPropagation();
    const pos = pointerToCanvas(event);
    if (!pos) {
        return;
    }
    selectedHandle = findNearestHandle(pos.x, pos.y);
    if (!selectedHandle) {
        drawOverlay();
        updateButtons();
        setHint("No editable handle nearby. Try clicking closer to a labeled point.");
        return;
    }
    updateButtons();
    draggingPointerId = event.pointerId;
    overlay.setPointerCapture(event.pointerId);
    overlay.style.cursor = "grabbing";
    moveSelectedHandle(pos.x, pos.y);
});

overlay.addEventListener("pointermove", (event) => {
    if (!isEditing || draggingPointerId !== event.pointerId || !selectedHandle) {
        return;
    }
    event.preventDefault();
    event.stopPropagation();
    const pos = pointerToCanvas(event);
    if (pos) {
        moveSelectedHandle(pos.x, pos.y);
    }
});

overlay.addEventListener("pointerup", (event) => {
    if (!isEditing || draggingPointerId !== event.pointerId) {
        return;
    }
    event.preventDefault();
    event.stopPropagation();
    draggingPointerId = null;
    overlay.releasePointerCapture(event.pointerId);
    overlay.style.cursor = "grab";
    drawOverlay();
});

overlay.addEventListener("pointercancel", (event) => {
    if (draggingPointerId === event.pointerId) {
        draggingPointerId = null;
        overlay.style.cursor = "grab";
    }
});

toggleBtn?.addEventListener("click", (event) => {
    event.stopPropagation();
    if (isEditing) {
        cancelEditing();
    } else {
        startEditing();
    }
});

saveBtn?.addEventListener("click", (event) => {
    event.stopPropagation();
    void saveEditing();
});

cancelBtn?.addEventListener("click", (event) => {
    event.stopPropagation();
    cancelEditing();
});

addBtn?.addEventListener("click", (event) => {
    event.stopPropagation();
    addSelectedTool();
});

deleteBtn?.addEventListener("click", (event) => {
    event.stopPropagation();
    deleteSelectedTool();
});

applyRopeBtn?.addEventListener("click", (event) => {
    event.stopPropagation();
    applySelectedRopeSettings();
});

ropeTensionSelect?.addEventListener("change", (event) => {
    event.stopPropagation();
    previewSelectedRopeTension();
});

window.addEventListener("resize", () => {
    if (!isEditing) {
        return;
    }
    syncOverlayRect();
    drawOverlay();
});

function animationLoop(): void {
    if (isEditing) {
        syncOverlayRect();
        freezeSceneForEdit();
        drawOverlay();
    }
    requestAnimationFrame(animationLoop);
}

updateButtons();
requestAnimationFrame(animationLoop);
console.log("[LevelEditorUI] Level editor initialized");
