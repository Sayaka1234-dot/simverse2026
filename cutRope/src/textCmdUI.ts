/**
 * textCmdUI.ts - 文本指令面板逻辑。
 */

import textCommandController, { type Command, type Condition } from "@/game/TextCommandController";
import manualCommandRecorder from "@/game/ManualCommandRecorder";
import ctrRootController from "@/game/CTRRootController";
import GameView from "@/game/GameView";
import LevelState from "@/game/LevelState";
import PubSub from "@/utils/PubSub";
import type GameScene from "@/GameScene";
import type GameController from "@/game/GameController";
import type { LevelWonInfo } from "@/ui/InterfaceManager/gameFlow";
import type { LevelJson } from "@/types/json";

const panel = document.getElementById("textCmdPanel") as HTMLDivElement;
const toggle = document.getElementById("textCmdToggle") as HTMLDivElement;
const input = document.getElementById("textCmdInput") as HTMLTextAreaElement;
const runBtn = document.getElementById("textCmdRun") as HTMLButtonElement;
const stopBtn = document.getElementById("textCmdStop") as HTMLButtonElement;
const submitBtn = document.getElementById("textCmdSubmit") as HTMLButtonElement;
const statusDiv = document.getElementById("textCmdStatus") as HTMLDivElement;
const candyPosDiv = document.getElementById("textCmdCandyPos") as HTMLDivElement;
const submitHintDiv = document.getElementById("textCmdSubmitHint") as HTMLDivElement;

let panelOpen = false;
const SAVE_ENDPOINT = "/__codex/save-level-solution";

type PendingRun = {
    levelId: string;
    commands: string;
};

type EligibleSubmission = {
    levelId: string;
    commands: string;
    stars: number;
};

let pendingRun: PendingRun | null = null;
let eligibleSubmission: EligibleSubmission | null = null;
let isSubmitting = false;
let submitNotice: string | null = null;
let lastSeenLevelId: string | null = null;

function setPanelOpen(open: boolean): void {
    panelOpen = open;
    panel.style.transform = open
        ? "translateY(-50%) translateX(0)"
        : "translateY(-50%) translateX(100%)";
}

setPanelOpen(false);

toggle.addEventListener("click", (e) => {
    e.stopPropagation();
    setPanelOpen(!panelOpen);
});

for (const eventName of [
    "mousedown",
    "mousemove",
    "mouseup",
    "touchstart",
    "touchmove",
    "touchend",
    "click",
    "pointerdown",
    "pointermove",
    "pointerup",
]) {
    panel.addEventListener(eventName, (e) => e.stopPropagation());
}

input.addEventListener("focus", () => {
    input.style.borderColor = "rgba(100, 200, 255, 0.5)";
});
input.addEventListener("blur", () => {
    input.style.borderColor = "rgba(100, 200, 255, 0.2)";
});

function appendRecordedCommand(line: string): void {
    const current = input.value.trimEnd();
    input.value = current ? `${current}\n${line}` : line;
    input.dispatchEvent(new Event("input", { bubbles: true }));
}

manualCommandRecorder.setCommandSink(appendRecordedCommand);

function getCurrentLevelData(): LevelJson | null {
    return LevelState.loadedMap;
}

function getCurrentLevelId(): string | null {
    const level = getCurrentLevelData();
    if (!level || typeof level.levelId !== "string" || !level.levelId.trim()) {
        return null;
    }
    return level.levelId.trim();
}

function getSavedSolution(): string | null {
    const level = getCurrentLevelData();
    if (!level || typeof level.textCommandSolution !== "string") {
        return null;
    }
    const trimmed = level.textCommandSolution.trim();
    return trimmed ? trimmed : null;
}

function clearSubmitNotice(): void {
    submitNotice = null;
}

function resetSubmissionProgress(): void {
    pendingRun = null;
    eligibleSubmission = null;
}

function updateSubmitUI(): void {
    const levelId = getCurrentLevelId();
    const hasInput = input.value.trim().length > 0;
    const savedSolution = getSavedSolution();
    const canSubmit = Boolean(eligibleSubmission) && !isSubmitting;

    submitBtn.disabled = !canSubmit;
    submitBtn.style.opacity = canSubmit ? "1" : "0.45";
    submitBtn.style.cursor = canSubmit ? "pointer" : "not-allowed";
    submitBtn.textContent = isSubmitting ? "Saving..." : "Submit 3-Star Answer";

    if (submitNotice) {
        submitHintDiv.textContent = submitNotice;
        return;
    }

    if (!levelId) {
        submitHintDiv.textContent = "Open a level to enable answer submission.";
        return;
    }

    if (eligibleSubmission) {
        submitHintDiv.textContent = `3-star clear confirmed for ${levelId}. Click Submit to save this command sequence into ${levelId}.json.`;
        return;
    }

    if (!hasInput) {
        submitHintDiv.textContent = `Level ${levelId} is loaded. Enter commands first.`;
        return;
    }

    if (savedSolution) {
        submitHintDiv.textContent = `Level ${levelId} already has a saved answer. A new 3-star clear will overwrite it.`;
        return;
    }

    if (pendingRun && pendingRun.levelId === levelId) {
        submitHintDiv.textContent = `Commands are running for ${levelId}. Submit unlocks only after a 3-star clear.`;
        return;
    }

    submitHintDiv.textContent = `Level ${levelId} is ready. Submit unlocks only after a 3-star clear with the current command text.`;
}

function setSubmitNotice(message: string): void {
    submitNotice = message;
    updateSubmitUI();
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

function formatConditionText(cond: Condition, parentType: "and" | "or" | null = null): string {
    const candyPrefix = cond.candyTarget ? `${cond.candyTarget}_` : "";

    switch (cond.type) {
        case "none":
            return "";
        case "and":
        case "or": {
            const groupType: "and" | "or" = cond.type;
            const joiner = ` ${groupType} `;
            const current = (cond.conditions ?? [])
                .map((child) => formatConditionText(child, groupType))
                .filter(Boolean)
                .join(joiner);
            if (!current) {
                return "";
            }
            if (parentType && parentType !== groupType) {
                return `(${current})`;
            }
            return current;
        }
        case "candy_y_gt":
            return `${candyPrefix}candy_y > ${cond.value}`;
        case "candy_y_lt":
            return `${candyPrefix}candy_y < ${cond.value}`;
        case "candy_x_gt":
            return `${candyPrefix}candy_x > ${cond.value}`;
        case "candy_x_lt":
            return `${candyPrefix}candy_x < ${cond.value}`;
        case "grab_x_gt":
            return `grab_x ${cond.targetIndex} > ${cond.value}`;
        case "grab_x_lt":
            return `grab_x ${cond.targetIndex} < ${cond.value}`;
        case "grab_y_gt":
            return `grab_y ${cond.targetIndex} > ${cond.value}`;
        case "grab_y_lt":
            return `grab_y ${cond.targetIndex} < ${cond.value}`;
        case "obj_x_gt":
            return `obj_x ${cond.objectKind} ${cond.targetIndex} > ${cond.value}`;
        case "obj_x_lt":
            return `obj_x ${cond.objectKind} ${cond.targetIndex} < ${cond.value}`;
        case "obj_y_gt":
            return `obj_y ${cond.objectKind} ${cond.targetIndex} > ${cond.value}`;
        case "obj_y_lt":
            return `obj_y ${cond.objectKind} ${cond.targetIndex} < ${cond.value}`;
        case "candy_near": {
            let text = `${candyPrefix}candy_near ${cond.x},${cond.y},${cond.radius}`;
            if (cond.count && cond.count > 1) {
                text += ` times ${cond.count}`;
            }
            return text;
        }
        case "candy_near_for":
            return `${candyPrefix}candy_near ${cond.x},${cond.y},${cond.radius} for ${cond.duration}`;
        case "candy_still_for": {
            let text = `${candyPrefix}candy_still for ${cond.duration}`;
            if (cond.threshold !== undefined) {
                text += ` speed ${cond.threshold}`;
            }
            return text;
        }
        case "grab_near": {
            let text = `grab_near ${cond.targetIndex},${cond.x},${cond.y},${cond.radius}`;
            if (cond.count && cond.count > 1) {
                text += ` times ${cond.count}`;
            }
            return text;
        }
        case "grab_near_for":
            return `grab_near ${cond.targetIndex},${cond.x},${cond.y},${cond.radius} for ${cond.duration}`;
        case "obj_near": {
            let text = `obj_near ${cond.objectKind} ${cond.targetIndex},${cond.x},${cond.y},${cond.radius}`;
            if (cond.count && cond.count > 1) {
                text += ` times ${cond.count}`;
            }
            return text;
        }
        case "obj_near_for":
            return `obj_near ${cond.objectKind} ${cond.targetIndex},${cond.x},${cond.y},${cond.radius} for ${cond.duration}`;
        case "rope_cut":
            return `rope_cut ${cond.value}`;
        case "no_rope":
            return "no_rope";
        case "wait_frames":
            return `wait_frames ${cond.value}`;
        case "candy_vy_gt":
            return `${candyPrefix}candy_velocity_y > ${cond.value}`;
        case "candy_vy_lt":
            return `${candyPrefix}candy_velocity_y < ${cond.value}`;
        case "candy_in_bubble":
            return `${candyPrefix}candy_in_bubble`;
        case "candy_in_lantern":
            return "candy_in_lantern";
        case "lantern_has_candy":
            return `lantern_has_candy ${cond.targetIndex}`;
        case "mouse_has_candy":
            return "mouse_has_candy";
        default:
            return "";
    }
}

function formatCommandText(cmd: Command): string {
    let cmdText = cmd.action;

    switch (cmd.action) {
        case "cut_rope":
            cmdText += ` ${(cmd.targetIndices ?? [cmd.targetIndex]).join(",")}`;
            break;
        case "fire_gun":
        case "pop_lightbulb_bubble":
        case "tap_ghost":
        case "toggle_steam_tube":
        case "release_lantern":
        case "stop_rotate_circle":
        case "stop_rotate_wheel":
        case "kick_rope":
            cmdText += ` ${cmd.targetIndex}`;
            break;
        case "pop_bubble":
            if (cmd.targetIndex >= 0) {
                cmdText += ` ${cmd.targetIndex}`;
            }
            break;
        case "activate_pump":
            cmdText += ` ${cmd.targetIndex}`;
            if (cmd.repeatCount !== undefined) {
                cmdText += ` times ${cmd.repeatCount}`;
            }
            if (cmd.repeatInterval !== undefined && (cmd.repeatCount !== undefined || cmd.untilCondition)) {
                cmdText += ` every ${cmd.repeatInterval}`;
            }
            if (cmd.untilCondition) {
                cmdText += ` until ${formatConditionText(cmd.untilCondition)}`;
            }
            break;
        case "rotate_circle":
            cmdText += ` ${cmd.targetIndex}`;
            if (cmd.direction) {
                cmdText += ` ${cmd.direction}`;
            }
            if (cmd.value !== undefined) {
                cmdText += ` ${cmd.value}`;
            }
            break;
        case "rotate_wheel":
            cmdText += ` ${cmd.targetIndex}`;
            if (cmd.wheelMode) {
                cmdText += ` ${cmd.wheelMode}`;
            } else if (cmd.value !== undefined) {
                cmdText += ` ${cmd.value}`;
            }
            break;
        case "drag_conveyor":
            cmdText += ` ${cmd.targetIndex} ${cmd.value}`;
            break;
        case "move_grab":
            cmdText += ` ${cmd.targetIndex} ${cmd.value}`;
            if (cmd.value2 !== undefined) {
                cmdText += ` ${cmd.value2}`;
            }
            break;
        default:
            break;
    }

    if (cmd.condition.type !== "none") {
        cmdText += ` when ${formatConditionText(cmd.condition)}`;
    }

    return cmdText;
}

runBtn.addEventListener("click", () => {
    const text = input.value.trim();
    if (!text) {
        statusDiv.innerHTML = '<span style="color: #f39c12;">No runnable commands</span>';
        clearSubmitNotice();
        resetSubmissionProgress();
        updateSubmitUI();
        return;
    }

    clearSubmitNotice();
    resetSubmissionProgress();
    textCommandController.load(text);
    textCommandController.start();

    const levelId = getCurrentLevelId();
    if (textCommandController.status !== "error" && levelId) {
        pendingRun = { levelId, commands: text };
    }

    runBtn.style.opacity = "0.5";
    stopBtn.style.opacity = "1";

    updateStatusDisplay();
    updateSubmitUI();
});

stopBtn.addEventListener("click", () => {
    textCommandController.stop();
    clearSubmitNotice();
    resetSubmissionProgress();
    runBtn.style.opacity = "1";
    stopBtn.style.opacity = "0.5";
    statusDiv.innerHTML = '<span style="opacity: 0.5;">Stopped. Enter commands and click Run.</span>';
    setSubmitNotice("Command run stopped. Submit is locked until a fresh 3-star clear.");
});

textCommandController.onStatusChange = () => {
    if (textCommandController.status === "error") {
        resetSubmissionProgress();
        setSubmitNotice("Command parse error. Fix the command sequence before submitting.");
    } else if (textCommandController.status === "running") {
        updateSubmitUI();
    }
    updateStatusDisplay();
};

input.addEventListener("input", () => {
    clearSubmitNotice();
    resetSubmissionProgress();
    updateSubmitUI();
});

PubSub.subscribe(PubSub.ChannelId.LevelWon, (...args: unknown[]) => {
    const [info] = args as [LevelWonInfo];
    const levelId = getCurrentLevelId();
    const currentCommands = input.value.trim();

    if (!levelId || !pendingRun || pendingRun.levelId !== levelId || pendingRun.commands !== currentCommands) {
        if (info?.stars === 3) {
            setSubmitNotice("3-star clear detected, but the current command text does not match the last executed run.");
        }
        return;
    }

    if (info.stars === 3) {
        eligibleSubmission = {
            levelId,
            commands: pendingRun.commands,
            stars: info.stars,
        };
        setSubmitNotice(`3-star clear confirmed for ${levelId}. Click Submit to save this command sequence.`);
        return;
    }

    eligibleSubmission = null;
    setSubmitNotice(`Level cleared with ${info.stars} star(s). Submit stays locked until you reach 3 stars.`);
});

PubSub.subscribe(PubSub.ChannelId.LevelLost, () => {
    if (!pendingRun) {
        return;
    }
    eligibleSubmission = null;
    setSubmitNotice("Run ended without a clear. Adjust the commands and try again.");
});

submitBtn.addEventListener("click", async () => {
    if (!eligibleSubmission || isSubmitting) {
        updateSubmitUI();
        return;
    }

    const payload = {
        levelId: eligibleSubmission.levelId,
        commands: eligibleSubmission.commands,
        stars: eligibleSubmission.stars,
        won: true,
    };
    const levelFile = `${eligibleSubmission.levelId}.json`;

    isSubmitting = true;
    clearSubmitNotice();
    updateSubmitUI();

    try {
        const response = await fetch(SAVE_ENDPOINT, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
        });

        const raw = (await response.json().catch(() => null)) as
            | {
                  error?: string;
                  updatedAt?: string;
              }
            | null;

        if (!response.ok) {
            throw new Error(raw?.error || `Save request failed with status ${response.status}`);
        }

        const level = getCurrentLevelData();
        if (level) {
            level.textCommandSolution = payload.commands;
            level.textCommandSolutionStars = payload.stars;
            level.textCommandSolutionWon = true;
            level.textCommandSolutionUpdatedAt =
                typeof raw?.updatedAt === "string" ? raw.updatedAt : new Date().toISOString();
        }

        resetSubmissionProgress();
        setSubmitNotice(`Saved answer to ${levelFile}. Future 3-star submissions will overwrite it.`);
    } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        setSubmitNotice(`Failed to save answer: ${message}`);
    } finally {
        isSubmitting = false;
        updateSubmitUI();
    }
});
function updateStatusDisplay(): void {
    const commands = textCommandController.commandList;
    const status = textCommandController.status;

    if (commands.length === 0) {
        statusDiv.innerHTML = '<span style="opacity: 0.5;">空闲中，输入指令后点击运行</span>';
        return;
    }

    let html = "";
    const statusColors: Record<string, string> = {
        idle: "#7f8c8d",
        running: "#2ecc71",
        finished: "#3498db",
        error: "#e74c3c",
    };
    const statusLabels: Record<string, string> = {
        idle: "空闲",
        running: "运行中",
        finished: "已完成",
        error: "错误",
    };
    const statusColor = statusColors[status] ?? "#7f8c8d";
    const statusLabel = statusLabels[status] ?? status;

    html += `<div style="margin-bottom: 8px; color: ${statusColor}; font-weight: 600;">状态: ${statusLabel}</div>`;

    for (const cmd of commands) {
        let icon = "-";
        let color = "#7f8c8d";
        let bg = "transparent";

        switch (cmd.status) {
            case "done":
                icon = "OK";
                color = "#2ecc71";
                bg = "rgba(46, 204, 113, 0.08)";
                break;
            case "running":
                icon = "RUN";
                color = "#3498db";
                bg = "rgba(52, 152, 219, 0.12)";
                break;
            case "waiting":
                icon = "...";
                color = "#f1c40f";
                bg = "rgba(241, 196, 15, 0.08)";
                break;
            case "error":
                icon = "ERR";
                color = "#e74c3c";
                bg = "rgba(231, 76, 60, 0.08)";
                break;
            default:
                break;
        }

        html += `<div style="
            padding: 3px 6px;
            margin: 2px 0;
            border-radius: 4px;
            background: ${bg};
            color: ${color};
            display: flex;
            gap: 6px;
            align-items: baseline;
        ">
            <span style="width: 24px; flex-shrink: 0; font-size: 10px;">${icon}</span>
            <span style="opacity: ${cmd.status === "pending" ? 0.5 : 1};">${formatCommandText(cmd)}</span>
        </div>`;

        if (cmd.status === "error" && cmd.errorMsg) {
            html += `<div style="color: #e74c3c; padding-left: 30px; font-size: 10px;">${cmd.errorMsg}</div>`;
        }
    }

    statusDiv.innerHTML = html;
    statusDiv.scrollTop = statusDiv.scrollHeight;

    if (status === "finished" || status === "error" || status === "idle") {
        runBtn.style.opacity = "1";
        stopBtn.style.opacity = "0.5";
    }
}

let posUpdateCounter = 0;

function updateCandyPosition(): void {
    posUpdateCounter++;

    const levelId = getCurrentLevelId();
    if (levelId !== lastSeenLevelId) {
        lastSeenLevelId = levelId;
        clearSubmitNotice();
        resetSubmissionProgress();
        updateSubmitUI();
    }

    if (posUpdateCounter % 5 !== 0) {
        requestAnimationFrame(updateCandyPosition);
        return;
    }

    const scene = getGameScene();
    if (scene?.star) {
        const x = Math.round(scene.star.pos.x);
        const y = Math.round(scene.star.pos.y);
        const vy = scene.star.v ? scene.star.v.y.toFixed(1) : "--";
        candyPosDiv.textContent = `x: ${x} , y: ${y} , vy: ${vy}`;
    } else {
        candyPosDiv.textContent = "x: -- , y: -- , vy: --";
    }

    requestAnimationFrame(updateCandyPosition);
}

requestAnimationFrame(updateCandyPosition);
updateSubmitUI();
console.log("[TextCmdUI] Text Command Panel initialized");
