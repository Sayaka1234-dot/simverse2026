/**
 * TextCommandController - Event-driven text command interface for Cut the Rope.
 *
 * Allows controlling the game through text-based instructions with
 * spatial/state conditions instead of time-based triggers.
 *
 * Syntax:
 *   ACTION [when CONDITION]
 *
 * Actions:
 *   cut_rope N[,M...]      - Cut one or more ropes by index (0-based)
 *   pop_bubble             - Pop the candy's current bubble (backward compat)
 *   pop_bubble N           - Pop free bubble N by index (bubbles[N], labeled B0, B1...)
 *   pop_bubble_left        - Pop the left candy bubble (split levels)
 *   pop_bubble_right       - Pop the right candy bubble (split levels)
 *   pop_lightbulb_bubble N - Pop the bubble captured by lightbulb index N
 *   toggle_gravity         - Toggle gravity direction
 *   activate_pump N        - Activate pump by index once
 *   activate_pump N times C - Activate pump C times
 *   activate_pump N times C every S - Activate pump C times, once every S seconds
 *   activate_pump N until CONDITION - Keep activating pump until CONDITION becomes true
 *   activate_pump N every S until CONDITION - Keep activating pump every S seconds until CONDITION becomes true
 *   fire_gun N             - Fire a gun-type rope anchor
 *   tap_ghost N            - Cycle ghost state by index
 *   toggle_steam_tube N    - Toggle steam tube by index
 *   release_lantern N      - Tap lantern N to release the main candy
 *   rotate_circle N cw     - Start rotating turntable N clockwise
 *   rotate_circle N ccw    - Start rotating turntable N counterclockwise
 *   rotate_circle N cw D   - Rotate turntable N clockwise by D degrees once
 *   rotate_circle N ccw D  - Rotate turntable N counterclockwise by D degrees once
 *   stop_rotate_circle N   - Stop turntable N rotation
 *   rotate_wheel N extend  - Start extending rope wheel N
 *   rotate_wheel N shorten - Start shortening rope wheel N
 *   stop_rotate_wheel N    - Stop rope wheel N
 *   move_grab N X [Y]      - Move a movable grab to X (or Y if vertical)
 *   kick_rope N            - Kick (release) a sticky rope by index
 *   tap_mouse              - Tap active mouse to drop candy (if held)
 *   drag_conveyor N D      - Drag manual conveyor N by distance D
 *
 * Conditions:
 *   when candy_y > N           - Candy below y threshold
 *   when candy_y < N           - Candy above y threshold
 *   when candy_x > N           - Candy right of x threshold
 *   when candy_x < N           - Candy left of x threshold
 *   when candy_near X,Y,R      - Candy within radius R of (X,Y)
 *   when candy_near X,Y,R times N - Trigger on the Nth entry into the region
 *   when candy_near X,Y,R for S   - Candy stays inside region for S seconds
 *   when candy_still for S     - Candy final position stays stable for S seconds
 *   when grab_x I > N           - Grab/hook I is right of x threshold
 *   when grab_x I < N           - Grab/hook I is left of x threshold
 *   when grab_y I > N           - Grab/hook I is below y threshold
 *   when grab_y I < N           - Grab/hook I is above y threshold
 *   when grab_near I,X,Y,R      - Grab/hook I within radius R of (X,Y)
 *   when grab_near I,X,Y,R times N - Trigger on Nth entry of grab/hook I
 *   when grab_near I,X,Y,R for S   - Grab/hook I stays inside region for S seconds
 *   when obj_x KIND I > N       - Numbered object KIND I is right of x threshold
 *   when obj_x KIND I < N       - Numbered object KIND I is left of x threshold
 *   when obj_y KIND I > N       - Numbered object KIND I is below y threshold
 *   when obj_y KIND I < N       - Numbered object KIND I is above y threshold
 *   when obj_near KIND I,X,Y,R  - Numbered object KIND I is within radius R of (X,Y)
 *   when obj_near KIND I,X,Y,R times N - Trigger on the Nth entry into the region
 *   when obj_near KIND I,X,Y,R for S   - Object KIND I stays inside region for S seconds
 *   when rope_cut N            - After rope N has been cut
 *   when no_rope               - Candy has no ropes attached
 *   when wait_frames N         - Wait N physics frames after previous command
 *   when candy_velocity_y > N  - Candy vertical velocity exceeds threshold
 *   when candy_velocity_y < N  - Candy vertical velocity below threshold
 *   when candy_in_bubble       - Candy is inside a bubble
 *   when candy_in_lantern      - The main candy is currently stored in a lantern
 *   when mouse_has_candy       - Active mouse is carrying candy
 *   when A and B               - Both conditions must be true
 *   when A or B                - Any condition can be true
 *   when (A and B) or C        - Parentheses can group composite conditions
 */

import Gravity from "@/physics/Gravity";
import Constants from "@/utils/Constants";
import Bungee from "@/game/Bungee";
import MathHelper from "@/utils/MathHelper";
import SoundMgr from "@/game/CTRSoundMgr";
import ResourceId from "@/resources/ResourceId";
import GravityButton from "@/game/GravityButton";
import Radians from "@/utils/Radians";
import Vector from "@/core/Vector";
import Rectangle from "@/core/Rectangle";
import { PUMP_TIMEOUT, PartsType } from "@/gameScene/constants";
import type { GameScene } from "@/types/game-scene";

// ─── Types ────────────────────────────────────────────────────────────

export type ActionType =
    | "cut_rope"
    | "pop_bubble"
    | "pop_bubble_left"
    | "pop_bubble_right"
    | "pop_lightbulb_bubble"
    | "toggle_gravity"
    | "activate_pump"
    | "fire_gun"
    | "tap_ghost"
    | "toggle_steam_tube"
    | "release_lantern"
    | "rotate_circle"
    | "stop_rotate_circle"
    | "rotate_wheel"
    | "stop_rotate_wheel"
    | "move_grab"
    | "kick_rope"
    | "tap_mouse"
    | "drag_conveyor";

export type TrackableKind =
    | "rope"
    | "pump"
    | "ghost"
    | "valve"
    | "lantern"
    | "lightbulb"
    | "spike"
    | "hat"
    | "bouncer"
    | "circle"
    | "mouse"
    | "conveyor"
    | "gravity"
    | "bubble";

export type CandyTarget = "left" | "right";

export type ConditionType =
    | "none"
    | "and"
    | "or"
    | "candy_y_gt"
    | "candy_y_lt"
    | "candy_x_gt"
    | "candy_x_lt"
    | "candy_near"
    | "candy_near_for"
    | "candy_still_for"
    | "grab_x_gt"
    | "grab_x_lt"
    | "grab_y_gt"
    | "grab_y_lt"
    | "grab_near"
    | "grab_near_for"
    | "obj_x_gt"
    | "obj_x_lt"
    | "obj_y_gt"
    | "obj_y_lt"
    | "obj_near"
    | "obj_near_for"
    | "rope_cut"
    | "no_rope"
    | "wait_frames"
    | "candy_vy_gt"
    | "candy_vy_lt"
    | "candy_in_bubble"
    | "candy_in_lantern"
    | "lantern_has_candy"
    | "mouse_has_candy";

export interface Condition {
    type: ConditionType;
    conditions?: Condition[];
    targetIndex?: number;
    objectKind?: TrackableKind;
    candyTarget?: CandyTarget | undefined;
    value?: number;
    x?: number;
    y?: number;
    radius?: number;
    count?: number;
    duration?: number;
    threshold?: number;
}

export interface Command {
    action: ActionType;
    targetIndex: number; // first/primary target index for legacy UI and single-target actions
    targetIndices?: number[]; // for multi-target cut_rope
    value?: number; // extra numeric parameter (degrees, distance, etc.)
    value2?: number; // optional second parameter (e.g., move_grab Y)
    direction?: "cw" | "ccw"; // for rotate_circle
    wheelMode?: "extend" | "shorten"; // for rotate_wheel
    repeatCount?: number; // for repeated activate_pump
    repeatInterval?: number; // seconds between repeated activate_pump clicks
    untilCondition?: Condition; // stop condition for repeated activate_pump
    condition: Condition;
    status: "pending" | "waiting" | "running" | "done" | "error";
    errorMsg?: string;
}

export type CommandStatus = "idle" | "running" | "finished" | "error";

// ─── Parse helpers ────────────────────────────────────────────────────

function validateConditionParentheses(condStr: string): void {
    let depth = 0;
    for (const ch of condStr) {
        if (ch === "(") {
            depth++;
        } else if (ch === ")") {
            depth--;
            if (depth < 0) {
                throw new Error(`Unmatched ")" in condition: "${condStr}"`);
            }
        }
    }
    if (depth !== 0) {
        throw new Error(`Unmatched "(" in condition: "${condStr}"`);
    }
}

function stripOuterConditionParens(condStr: string): string {
    let current = condStr.trim();

    while (current.startsWith("(") && current.endsWith(")")) {
        let depth = 0;
        let wrapsWholeString = true;

        for (let i = 0; i < current.length; i++) {
            const ch = current[i];
            if (ch === "(") {
                depth++;
            } else if (ch === ")") {
                depth--;
                if (depth === 0 && i < current.length - 1) {
                    wrapsWholeString = false;
                    break;
                }
            }
        }

        if (!wrapsWholeString) {
            break;
        }

        current = current.slice(1, -1).trim();
    }

    return current;
}

function splitTopLevelCondition(condStr: string, operator: "and" | "or"): string[] {
    const parts: string[] = [];
    const token = ` ${operator} `;
    let depth = 0;
    let start = 0;

    for (let i = 0; i < condStr.length; i++) {
        const ch = condStr[i];
        if (ch === "(") {
            depth++;
            continue;
        }
        if (ch === ")") {
            depth--;
            continue;
        }

        if (depth === 0 && condStr.startsWith(token, i)) {
            parts.push(condStr.slice(start, i).trim());
            start = i + token.length;
            i += token.length - 1;
        }
    }

    if (parts.length === 0) {
        return [condStr.trim()];
    }

    parts.push(condStr.slice(start).trim());
    return parts;
}

function parseCircleDirection(raw: string): "cw" | "ccw" {
    const normalized = raw.trim().toLowerCase();
    if (normalized === "cw" || normalized === "clockwise") {
        return "cw";
    }
    if (
        normalized === "ccw" ||
        normalized === "counterclockwise" ||
        normalized === "counter_clockwise" ||
        normalized === "anticlockwise" ||
        normalized === "anti_clockwise"
    ) {
        return "ccw";
    }
    throw new Error(
        `Invalid rotate_circle direction "${raw}". Use "cw", "ccw", "clockwise", or "counterclockwise"`
    );
}

function parseWheelMode(raw: string): "extend" | "shorten" {
    const normalized = raw.trim().toLowerCase();
    if (
        normalized === "extend" ||
        normalized === "lengthen" ||
        normalized === "loosen" ||
        normalized === "unwind"
    ) {
        return "extend";
    }
    if (
        normalized === "shorten" ||
        normalized === "tighten" ||
        normalized === "retract" ||
        normalized === "rewind"
    ) {
        return "shorten";
    }
    throw new Error(
        `Invalid rotate_wheel mode "${raw}". Use "extend", "shorten", "lengthen", or "tighten".`
    );
}

function parseTrackableKind(raw: string): TrackableKind {
    const normalized = raw.trim().toLowerCase();
    switch (normalized) {
        case "rope":
        case "grab":
        case "bungee":
            return "rope";
        case "pump":
            return "pump";
        case "ghost":
            return "ghost";
        case "valve":
        case "steam_valve":
        case "steam_tube":
        case "tube":
            return "valve";
        case "lantern":
            return "lantern";
        case "lightbulb":
        case "bulb":
            return "lightbulb";
        case "spike":
        case "spikes":
            return "spike";
        case "hat":
        case "sock":
        case "magic_hat":
            return "hat";
        case "bouncer":
        case "jump_pad":
        case "jumper":
            return "bouncer";
        case "circle":
        case "turntable":
        case "rotated_circle":
            return "circle";
        case "mouse":
        case "mice":
            return "mouse";
        case "conveyor":
        case "belt":
            return "conveyor";
        case "gravity":
        case "gravity_button":
            return "gravity";
        case "bubble":
            return "bubble";
        default:
            throw new Error(
                `Unknown object kind "${raw}". Use rope, pump, ghost, valve, lantern, lightbulb, spike, hat, bouncer, circle, mouse, conveyor, gravity, or bubble.`
            );
    }
}

function parseCandyTarget(raw: string | undefined): CandyTarget | undefined {
    if (raw === "left" || raw === "right") {
        return raw;
    }
    return undefined;
}

function parseSimpleCondition(condStr: string): Condition {
    // candy_y > N, left_candy_y > N, right_candy_y > N
    let m = condStr.match(/^(?:(left|right)_)?candy_y\s*([><])\s*(-?\d+(?:\.\d+)?)$/);
    if (m) {
        return {
            type: m[2] === ">" ? "candy_y_gt" : "candy_y_lt",
            candyTarget: parseCandyTarget(m[1]),
            value: parseFloat(m[3]!),
        };
    }

    // candy_x > N, left_candy_x > N, right_candy_x > N
    m = condStr.match(/^(?:(left|right)_)?candy_x\s*([><])\s*(-?\d+(?:\.\d+)?)$/);
    if (m) {
        return {
            type: m[2] === ">" ? "candy_x_gt" : "candy_x_lt",
            candyTarget: parseCandyTarget(m[1]),
            value: parseFloat(m[3]!),
        };
    }

    // grab_x I > N  or  grab_x I < N
    m = condStr.match(/^grab_x\s+(\d+)\s*([><])\s*(-?\d+(?:\.\d+)?)$/);
    if (m) {
        return {
            type: m[2] === ">" ? "grab_x_gt" : "grab_x_lt",
            targetIndex: parseInt(m[1]!, 10),
            value: parseFloat(m[3]!),
        };
    }

    // grab_y I > N  or  grab_y I < N
    m = condStr.match(/^grab_y\s+(\d+)\s*([><])\s*(-?\d+(?:\.\d+)?)$/);
    if (m) {
        return {
            type: m[2] === ">" ? "grab_y_gt" : "grab_y_lt",
            targetIndex: parseInt(m[1]!, 10),
            value: parseFloat(m[3]!),
        };
    }

    // obj_x KIND I > N  or  obj_x KIND I < N
    m = condStr.match(/^obj_x\s+([a-z_]+)\s+(\d+)\s*([><])\s*(-?\d+(?:\.\d+)?)$/i);
    if (m) {
        return {
            type: m[3] === ">" ? "obj_x_gt" : "obj_x_lt",
            objectKind: parseTrackableKind(m[1]!),
            targetIndex: parseInt(m[2]!, 10),
            value: parseFloat(m[4]!),
        };
    }

    // obj_y KIND I > N  or  obj_y KIND I < N
    m = condStr.match(/^obj_y\s+([a-z_]+)\s+(\d+)\s*([><])\s*(-?\d+(?:\.\d+)?)$/i);
    if (m) {
        return {
            type: m[3] === ">" ? "obj_y_gt" : "obj_y_lt",
            objectKind: parseTrackableKind(m[1]!),
            targetIndex: parseInt(m[2]!, 10),
            value: parseFloat(m[4]!),
        };
    }

    // candy_near X,Y,R [times N], left_candy_near ..., right_candy_near ...
    m = condStr.match(
        /^(?:(left|right)_)?candy_near\s+(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)(?:\s+times\s+(\d+))?$/
    );
    if (m) {
        const count = m[5] ? parseInt(m[5], 10) : 1;
        if (count <= 0 || Number.isNaN(count)) {
            throw new Error("candy_near times must be a positive integer");
        }
        return {
            type: "candy_near",
            candyTarget: parseCandyTarget(m[1]),
            x: parseFloat(m[2]!),
            y: parseFloat(m[3]!),
            radius: parseFloat(m[4]!),
            count,
        };
    }

    // candy_near X,Y,R for S, left_candy_near ..., right_candy_near ...
    m = condStr.match(
        /^(?:(left|right)_)?candy_near\s+(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s+for\s+(\d+(?:\.\d+)?)$/
    );
    if (m) {
        const duration = parseFloat(m[5]!);
        if (!Number.isFinite(duration) || duration <= 0) {
            throw new Error("candy_near for must be a positive number of seconds");
        }
        return {
            type: "candy_near_for",
            candyTarget: parseCandyTarget(m[1]),
            x: parseFloat(m[2]!),
            y: parseFloat(m[3]!),
            radius: parseFloat(m[4]!),
            duration,
        };
    }

    // candy_still for S [speed T], left_candy_still for ..., right_candy_still for ...
    m = condStr.match(
        /^(?:(left|right)_)?candy_still\s+for\s+(\d+(?:\.\d+)?)(?:\s+speed\s+(\d+(?:\.\d+)?))?$/
    );
    if (!m) {
        // Backward compatibility for older saved answers.
        m = condStr.match(
            /^(?:(left|right)_)?candy_still_for\s+(\d+(?:\.\d+)?)(?:\s+speed\s+(\d+(?:\.\d+)?))?$/
        );
    }
    if (m) {
        const duration = parseFloat(m[2]!);
        const threshold = m[3] !== undefined ? parseFloat(m[3]) : undefined;
        if (!Number.isFinite(duration) || duration <= 0) {
            throw new Error("candy_still for must be a positive number of seconds");
        }
        if (threshold !== undefined && (!Number.isFinite(threshold) || threshold < 0)) {
            throw new Error("candy_still for speed must be a non-negative number");
        }
        return {
            type: "candy_still_for",
            candyTarget: parseCandyTarget(m[1]),
            duration,
            ...(threshold !== undefined ? { threshold } : {}),
        };
    }

    // grab_near I,X,Y,R [times N]
    m = condStr.match(
        /^grab_near\s+(\d+)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)(?:\s+times\s+(\d+))?$/
    );
    if (m) {
        const count = m[5] ? parseInt(m[5], 10) : 1;
        if (count <= 0 || Number.isNaN(count)) {
            throw new Error("grab_near times must be a positive integer");
        }
        return {
            type: "grab_near",
            targetIndex: parseInt(m[1]!, 10),
            x: parseFloat(m[2]!),
            y: parseFloat(m[3]!),
            radius: parseFloat(m[4]!),
            count,
        };
    }

    // obj_near KIND I,X,Y,R [times N]
    m = condStr.match(
        /^obj_near\s+([a-z_]+)\s+(\d+)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)(?:\s+times\s+(\d+))?$/i
    );
    if (m) {
        const count = m[6] ? parseInt(m[6], 10) : 1;
        if (count <= 0 || Number.isNaN(count)) {
            throw new Error("obj_near times must be a positive integer");
        }
        return {
            type: "obj_near",
            objectKind: parseTrackableKind(m[1]!),
            targetIndex: parseInt(m[2]!, 10),
            x: parseFloat(m[3]!),
            y: parseFloat(m[4]!),
            radius: parseFloat(m[5]!),
            count,
        };
    }

    // grab_near I,X,Y,R for S (seconds)
    m = condStr.match(
        /^grab_near\s+(\d+)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s+for\s+(\d+(?:\.\d+)?)$/
    );
    if (m) {
        const duration = parseFloat(m[5]!);
        if (!Number.isFinite(duration) || duration <= 0) {
            throw new Error("grab_near for must be a positive number of seconds");
        }
        return {
            type: "grab_near_for",
            targetIndex: parseInt(m[1]!, 10),
            x: parseFloat(m[2]!),
            y: parseFloat(m[3]!),
            radius: parseFloat(m[4]!),
            duration,
        };
    }

    // obj_near KIND I,X,Y,R for S (seconds)
    m = condStr.match(
        /^obj_near\s+([a-z_]+)\s+(\d+)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s+for\s+(\d+(?:\.\d+)?)$/i
    );
    if (m) {
        const duration = parseFloat(m[6]!);
        if (!Number.isFinite(duration) || duration <= 0) {
            throw new Error("obj_near for must be a positive number of seconds");
        }
        return {
            type: "obj_near_for",
            objectKind: parseTrackableKind(m[1]!),
            targetIndex: parseInt(m[2]!, 10),
            x: parseFloat(m[3]!),
            y: parseFloat(m[4]!),
            radius: parseFloat(m[5]!),
            duration,
        };
    }

    // rope_cut N
    m = condStr.match(/^rope_cut\s+(\d+)$/);
    if (m) {
        return { type: "rope_cut", value: parseInt(m[1]!, 10) };
    }

    // no_rope
    if (condStr === "no_rope") {
        return { type: "no_rope" };
    }

    // wait_frames N
    m = condStr.match(/^wait_frames\s+(\d+)$/);
    if (m) {
        return { type: "wait_frames", value: parseInt(m[1]!, 10) };
    }

    // candy_velocity_y > N, left_candy_velocity_y > N, right_candy_velocity_y > N
    m = condStr.match(/^(?:(left|right)_)?candy_velocity_y\s*([><])\s*(-?\d+(?:\.\d+)?)$/);
    if (m) {
        return {
            type: m[2] === ">" ? "candy_vy_gt" : "candy_vy_lt",
            candyTarget: parseCandyTarget(m[1]),
            value: parseFloat(m[3]!),
        };
    }

    m = condStr.match(/^(?:(left|right)_)?candy_in_bubble$/);
    if (m) {
        return { type: "candy_in_bubble", candyTarget: parseCandyTarget(m[1]) };
    }

    if (condStr === "candy_in_lantern") {
        return { type: "candy_in_lantern" };
    }

    m = condStr.match(/^lantern_has_candy\s+(\d+)$/);
    if (m) {
        return { type: "lantern_has_candy", targetIndex: parseInt(m[1]!, 10) };
    }

    if (condStr === "mouse_has_candy") {
        return { type: "mouse_has_candy" };
    }

    throw new Error(`Unknown condition: "${condStr}"`);
}

function parseCondition(condStr: string): Condition {
    const trimmed = condStr.trim();
    validateConditionParentheses(trimmed);

    const normalized = stripOuterConditionParens(trimmed);

    const orParts = splitTopLevelCondition(normalized, "or");
    if (orParts.length > 1) {
        return {
            type: "or",
            conditions: orParts.map((part) => parseCondition(part)),
        };
    }

    const andParts = splitTopLevelCondition(normalized, "and");
    if (andParts.length > 1) {
        return {
            type: "and",
            conditions: andParts.map((part) => parseCondition(part)),
        };
    }

    return parseSimpleCondition(normalized);
}

function parseLine(line: string): Command | null {
    line = line.trim();

    // Skip empty lines and comments
    if (!line || line.startsWith("#") || line.startsWith("//")) {
        return null;
    }

    // Split on "when" keyword
    let actionPart: string;
    let condPart: string | null = null;
    const whenIdx = line.indexOf(" when ");
    if (whenIdx !== -1) {
        actionPart = line.substring(0, whenIdx).trim();
        condPart = line.substring(whenIdx + 5).trim();
    } else {
        actionPart = line;
    }

    const condition: Condition = condPart
        ? parseCondition(condPart)
        : { type: "none" };

    const tokens = actionPart.split(/\s+/);
    const actionName = tokens[0]!;
    const args = tokens.slice(1);

    const requireArg = (idx: number, name: string): string => {
        const value = args[idx];
        if (value == null || value === "") {
            throw new Error(`Missing ${name} for action "${actionName}"`);
        }
        return value;
    };

    const parseIntArg = (idx: number, name: string): number => {
        const raw = requireArg(idx, name);
        const value = parseInt(raw, 10);
        if (Number.isNaN(value)) {
            throw new Error(`Invalid ${name} "${raw}" for action "${actionName}"`);
        }
        return value;
    };

    const parseFloatArg = (idx: number, name: string): number => {
        const raw = requireArg(idx, name);
        const value = parseFloat(raw);
        if (Number.isNaN(value)) {
            throw new Error(`Invalid ${name} "${raw}" for action "${actionName}"`);
        }
        return value;
    };

    const parseIndexListArg = (name: string): number[] => {
        const raw = args.join(" ").trim();
        if (!raw) {
            throw new Error(`Missing ${name} for action "${actionName}"`);
        }

        const parts = raw.split(/[,\s]+/).filter(Boolean);
        const seen = new Set<number>();
        const values: number[] = [];

        for (const part of parts) {
            if (!/^\d+$/.test(part)) {
                throw new Error(`Invalid ${name} "${part}" for action "${actionName}"`);
            }
            const value = parseInt(part, 10);
            if (seen.has(value)) {
                continue;
            }
            seen.add(value);
            values.push(value);
        }

        if (values.length === 0) {
            throw new Error(`Missing ${name} for action "${actionName}"`);
        }
        return values;
    };

    let action: ActionType;
    let targetIndex = 0;
    let targetIndices: number[] | undefined;
    let value: number | undefined;
    let value2: number | undefined;
    let direction: "cw" | "ccw" | undefined;
    let wheelMode: "extend" | "shorten" | undefined;
    let repeatCount: number | undefined;
    let repeatInterval: number | undefined;
    let untilCondition: Condition | undefined;

    switch (actionName) {
        case "cut_rope":
            action = "cut_rope";
            targetIndices = parseIndexListArg("rope index");
            targetIndex = targetIndices[0]!;
            break;
        case "pop_bubble":
            action = "pop_bubble";
            if (args.length > 0 && args[0] !== "") {
                targetIndex = parseIntArg(0, "bubble index");
            } else {
                targetIndex = -1;
            }
            break;
        case "pop_bubble_left":
            action = "pop_bubble_left";
            break;
        case "pop_bubble_right":
            action = "pop_bubble_right";
            break;
        case "pop_lightbulb_bubble":
            action = "pop_lightbulb_bubble";
            targetIndex = parseIntArg(0, "lightbulb index");
            break;
        case "toggle_gravity":
            action = "toggle_gravity";
            break;
        case "activate_pump":
            action = "activate_pump";
            {
                const pumpMatch = actionPart.match(
                    /^activate_pump\s+(\d+)(?:\s+times\s+(\d+))?(?:\s+every\s+(\d+(?:\.\d+)?))?(?:\s+until\s+(.+))?$/
                );
                if (!pumpMatch) {
                    throw new Error(
                        'Invalid activate_pump syntax. Use "activate_pump N", "activate_pump N times C", "activate_pump N times C every S", "activate_pump N until CONDITION", or "activate_pump N every S until CONDITION"'
                    );
                }

                targetIndex = parseInt(pumpMatch[1]!, 10);
                if (Number.isNaN(targetIndex)) {
                    throw new Error(`Invalid pump index "${pumpMatch[1]}" for action "activate_pump"`);
                }

                if (pumpMatch[2] !== undefined) {
                    repeatCount = parseInt(pumpMatch[2], 10);
                    if (!Number.isInteger(repeatCount) || repeatCount <= 0) {
                        throw new Error("activate_pump times must be a positive integer");
                    }
                }

                if (pumpMatch[3] !== undefined) {
                    repeatInterval = parseFloat(pumpMatch[3]);
                    if (!Number.isFinite(repeatInterval) || repeatInterval <= 0) {
                        throw new Error("activate_pump every must be a positive number of seconds");
                    }
                }

                if (pumpMatch[4] !== undefined) {
                    untilCondition = parseCondition(pumpMatch[4]);
                }

                if (repeatCount !== undefined && untilCondition) {
                    throw new Error("activate_pump cannot use both times and until in the same command");
                }

                if (repeatInterval !== undefined && repeatCount === undefined && !untilCondition) {
                    throw new Error("activate_pump every requires either times or until");
                }

                if ((repeatCount !== undefined || untilCondition) && repeatInterval === undefined) {
                    repeatInterval = PUMP_TIMEOUT;
                }
            }
            break;
        case "fire_gun":
            action = "fire_gun";
            targetIndex = parseIntArg(0, "gun index");
            break;
        case "tap_ghost":
            action = "tap_ghost";
            targetIndex = parseIntArg(0, "ghost index");
            break;
        case "toggle_steam_tube":
            action = "toggle_steam_tube";
            targetIndex = parseIntArg(0, "tube index");
            break;
        case "release_lantern":
            action = "release_lantern";
            targetIndex = parseIntArg(0, "lantern index");
            break;
        case "rotate_circle":
            action = "rotate_circle";
            targetIndex = parseIntArg(0, "circle index");
            {
                const raw = requireArg(1, "direction");
                direction = parseCircleDirection(raw);
                if (args.length > 3) {
                    throw new Error(
                        'Invalid rotate_circle syntax. Use "rotate_circle N cw", "rotate_circle N ccw", "rotate_circle N cw D", or "rotate_circle N ccw D"'
                    );
                }
                if (args.length > 2) {
                    value = parseFloatArg(2, "degrees");
                }
            }
            break;
        case "stop_rotate_circle":
            action = "stop_rotate_circle";
            targetIndex = parseIntArg(0, "circle index");
            break;
        case "rotate_wheel":
            action = "rotate_wheel";
            targetIndex = parseIntArg(0, "rope index");
            {
                if (args.length !== 2) {
                    throw new Error(
                        'Invalid rotate_wheel syntax. Use "rotate_wheel N extend" or "rotate_wheel N shorten"'
                    );
                }
                const raw = requireArg(1, "mode");
                wheelMode = parseWheelMode(raw);
            }
            break;
        case "stop_rotate_wheel":
            action = "stop_rotate_wheel";
            targetIndex = parseIntArg(0, "rope index");
            break;
        case "move_grab":
            action = "move_grab";
            targetIndex = parseIntArg(0, "grab index");
            value = parseFloatArg(1, "position");
            if (args.length > 2) {
                value2 = parseFloatArg(2, "positionY");
            }
            break;
        case "kick_rope":
            action = "kick_rope";
            targetIndex = parseIntArg(0, "rope index");
            break;
        case "tap_mouse":
            action = "tap_mouse";
            break;
        case "drag_conveyor":
            action = "drag_conveyor";
            targetIndex = parseIntArg(0, "conveyor index");
            value = parseFloatArg(1, "distance");
            break;
        default:
            throw new Error(`Unknown action: "${actionName}"`);
    }

    return {
        action,
        targetIndex,
        ...(targetIndices !== undefined ? { targetIndices } : {}),
        ...(value !== undefined ? { value } : {}),
        ...(value2 !== undefined ? { value2 } : {}),
        ...(direction !== undefined ? { direction } : {}),
        ...(wheelMode !== undefined ? { wheelMode } : {}),
        ...(repeatCount !== undefined ? { repeatCount } : {}),
        ...(repeatInterval !== undefined ? { repeatInterval } : {}),
        ...(untilCondition ? { untilCondition } : {}),
        condition,
        status: "pending",
    };
}

// ─── Controller ───────────────────────────────────────────────────────

class TextCommandController {
    private static readonly CIRCLE_ROTATION_SPEED_DEG = 180;
    private static readonly WHEEL_ROTATION_SPEED_DEG = 180;
    private static readonly DEFAULT_STILL_SPEED_THRESHOLD = 5;

    private commands: Command[] = [];
    private currentIndex = 0;
    private _status: CommandStatus = "idle";
    private frameCounter = 0;
    private elapsedSeconds = 0;
    private _onStatusChange: (() => void) | null = null;
    private nearEntryCounts: Map<string, number> = new Map();
    private nearWasInside: Map<string, boolean> = new Map();
    private nearHoldSeconds: Map<string, number> = new Map();
    private stillHoldSeconds: Map<string, number> = new Map();
    private stillLastPositions: Map<string, { x: number; y: number }> = new Map();
    private waitStartFrames: Map<string, number> = new Map();
    private pumpClicksPerformed: Map<number, number> = new Map();
    private pumpNextClickAt: Map<number, number> = new Map();
    private activeCircleRotations: Map<number, 1 | -1> = new Map();
    private activeWheelRotations: Map<number, 1 | -1> = new Map();

    /** Rope indices that have been cut during this run */
    private cutRopes: Set<number> = new Set();

    get status(): CommandStatus {
        return this._status;
    }

    get currentCommandIndex(): number {
        return this.currentIndex;
    }

    get commandList(): ReadonlyArray<Command> {
        return this.commands;
    }

    set onStatusChange(cb: (() => void) | null) {
        this._onStatusChange = cb;
    }

    /**
     * Parse the text input and prepare commands for execution.
     */
    load(text: string): void {
        this.reset();
        const lines = text.split("\n");
        for (let i = 0; i < lines.length; i++) {
            try {
                const cmd = parseLine(lines[i]!);
                if (cmd) {
                    this.commands.push(cmd);
                }
            } catch (e) {
                const errCmd: Command = {
                    action: "cut_rope",
                    targetIndex: 0,
                    condition: { type: "none" },
                    status: "error",
                    errorMsg: `Line ${i + 1}: ${(e as Error).message}`,
                };
                this.commands.push(errCmd);
            }
        }
    }

    /**
     * Start executing loaded commands.
     */
    start(): void {
        if (this.commands.length === 0) {
            return;
        }

        // Check if there are parse errors
        const hasErrors = this.commands.some((c) => c.status === "error");
        if (hasErrors) {
            this._status = "error";
            this.notifyChange();
            return;
        }

        this._status = "running";
        this.currentIndex = 0;
        this.frameCounter = 0;
        this.elapsedSeconds = 0;
        this.cutRopes.clear();
        this.activeCircleRotations.clear();
        this.activeWheelRotations.clear();

        // Mark first command as waiting
        if (this.commands[0]) {
            this.commands[0].status = "waiting";
            this.resetConditionStateForCommand(0, this.commands[0].condition);
        }
        this.notifyChange();
    }

    /**
     * Stop execution and reset.
     */
    stop(): void {
        this.reset();
        this.notifyChange();
    }

    /**
     * Reset all state.
     */
    reset(): void {
        this.commands = [];
        this.currentIndex = 0;
        this._status = "idle";
        this.frameCounter = 0;
        this.elapsedSeconds = 0;
        this.cutRopes.clear();
        this.nearEntryCounts.clear();
        this.nearWasInside.clear();
        this.nearHoldSeconds.clear();
        this.stillHoldSeconds.clear();
        this.stillLastPositions.clear();
        this.waitStartFrames.clear();
        this.pumpClicksPerformed.clear();
        this.pumpNextClickAt.clear();
        this.activeCircleRotations.clear();
        this.activeWheelRotations.clear();
    }

    /**
     * Called every game frame to evaluate conditions and execute actions.
     */
    tick(scene: GameScene, delta: number): void {
        if (this._status !== "running") {
            return;
        }

        this.frameCounter++;
        const deltaSeconds =
            Number.isFinite(delta) && delta > 0 ? delta : 1 / 60;
        this.elapsedSeconds += deltaSeconds;

        if (this.currentIndex >= this.commands.length) {
            this._status = "finished";
            this.notifyChange();
            return;
        }

        const cmd = this.commands[this.currentIndex]!;

        if (this.isRepeatedPumpCommand(cmd)) {
            this.tickRepeatedPumpCommand(cmd, scene, deltaSeconds);
            if (this._status === "running") {
                this.tickActiveCircleRotations(scene, deltaSeconds);
                this.tickActiveWheelRotations(scene, deltaSeconds);
            }
            return;
        }

        // Evaluate condition
        if (this.evaluateCondition(cmd.condition, scene, this.getConditionKey(this.currentIndex), deltaSeconds)) {
            this.executeAction(cmd, scene, deltaSeconds);
            cmd.status = "done";
            this.advanceToNextCommand();
            this.notifyChange();
        }

        if (this._status === "running") {
            this.tickActiveCircleRotations(scene, deltaSeconds);
            this.tickActiveWheelRotations(scene, deltaSeconds);
        }
    }

    // ─── Private ───

    private getCandyPoint(target: CandyTarget | undefined, scene: GameScene): GameScene["star"] | null {
        if (target === "left") {
            return scene.twoParts !== PartsType.NONE && !scene.noCandyL ? scene.starL : null;
        }
        if (target === "right") {
            return scene.twoParts !== PartsType.NONE && !scene.noCandyR ? scene.starR : null;
        }
        return scene.noCandy ? null : scene.star;
    }

    private isCandyInBubble(target: CandyTarget | undefined, scene: GameScene): boolean {
        if (target === "left") {
            return Boolean(scene.candyBubbleL);
        }
        if (target === "right") {
            return Boolean(scene.candyBubbleR);
        }
        return Boolean(scene.candyBubble || scene.candyBubbleL || scene.candyBubbleR);
    }

    private lanternHasCandy(index: number | undefined, scene: GameScene): boolean {
        if (index === undefined || !scene.lanterns[index]) {
            return false;
        }
        return Boolean(scene.isCandyInLantern);
    }

    private getBubbleRuntimeBinding(
        index: number,
        scene: GameScene
    ): {
        bubble: NonNullable<GameScene["bubbles"][number]>;
        kind: "free" | "main" | "left" | "right" | "lightbulb";
        position: Vector;
        lightbulb?: NonNullable<GameScene["lightbulbs"][number]>;
    } | null {
        const bubble = scene.bubbles[index];
        if (!bubble) {
            return null;
        }

        const pointPosition = (
            point: { pos?: { x?: number; y?: number } } | null | undefined
        ): Vector => new Vector(point?.pos?.x ?? bubble.x, point?.pos?.y ?? bubble.y);

        if (scene.candyBubble === bubble) {
            return { bubble, kind: "main", position: pointPosition(scene.star) };
        }
        if (scene.candyBubbleL === bubble) {
            return { bubble, kind: "left", position: pointPosition(scene.starL) };
        }
        if (scene.candyBubbleR === bubble) {
            return { bubble, kind: "right", position: pointPosition(scene.starR) };
        }

        for (const bulb of scene.lightbulbs) {
            if (bulb?.capturingBubble === bubble) {
                const constraintPos = bulb.constraint?.pos;
                return {
                    bubble,
                    kind: "lightbulb",
                    lightbulb: bulb,
                    position: new Vector(constraintPos?.x ?? bulb.x, constraintPos?.y ?? bulb.y),
                };
            }
        }

        if (!bubble.popped) {
            return { bubble, kind: "free", position: new Vector(bubble.x, bubble.y) };
        }

        return null;
    }

    private getTrackablePosition(
        objectKind: TrackableKind | undefined,
        index: number | undefined,
        scene: GameScene
    ): Vector | null {
        if (objectKind == null || index == null) {
            return null;
        }

        switch (objectKind) {
            case "rope": {
                const grab = scene.bungees[index];
                if (!grab) {
                    return null;
                }
                if (grab.rope) {
                    return grab.rope.bungeeAnchor.pos.copy();
                }
                return new Vector(grab.x, grab.y);
            }
            case "pump": {
                const pump = scene.pumps[index];
                return pump ? new Vector(pump.x, pump.y) : null;
            }
            case "ghost": {
                const ghost = scene.ghosts[index];
                return ghost ? new Vector(ghost.x, ghost.y) : null;
            }
            case "valve": {
                const tube = scene.tubes[index];
                return tube ? tube.getValveWorldPosition() : null;
            }
            case "lantern": {
                const lantern = scene.lanterns[index];
                return lantern ? new Vector(lantern.x, lantern.y) : null;
            }
            case "lightbulb": {
                const bulb = scene.lightbulbs[index];
                return bulb ? new Vector(bulb.x, bulb.y) : null;
            }
            case "spike": {
                const spike = scene.spikes[index];
                return spike ? new Vector(spike.x, spike.y) : null;
            }
            case "hat": {
                const sock = scene.socks[index];
                return sock ? new Vector(sock.x, sock.y) : null;
            }
            case "bouncer": {
                const bouncer = scene.bouncers[index];
                return bouncer ? new Vector(bouncer.x, bouncer.y) : null;
            }
            case "circle": {
                const circle = scene.rotatedCircles[index];
                return circle ? new Vector(circle.x, circle.y) : null;
            }
            case "mouse": {
                const mouse = scene.mice[index];
                return mouse ? new Vector(mouse.x, mouse.y) : null;
            }
            case "conveyor": {
                const belt = Array.from(scene.conveyors.iterator())[index];
                if (!belt) {
                    return null;
                }
                return new Vector(
                    belt.x + belt.direction.x * (belt.width / 2),
                    belt.y + belt.direction.y * (belt.width / 2)
                );
            }
            case "gravity": {
                if (index !== 0 || !scene.gravityButton) {
                    return null;
                }
                return new Vector(scene.gravityButton.x, scene.gravityButton.y);
            }
            case "bubble": {
                return this.getBubbleRuntimeBinding(index, scene)?.position ?? null;
            }
            default:
                return null;
        }
    }

    private evaluateNearConditionAtPosition(
        x: number,
        y: number,
        cond: Condition,
        conditionKey: string
    ): boolean {
        const dx = x - cond.x!;
        const dy = y - cond.y!;
        const distSq = dx * dx + dy * dy;
        const inside = distSq <= cond.radius! * cond.radius!;
        const count = cond.count ?? 1;
        if (count <= 1) {
            return inside;
        }

        const wasInside = this.nearWasInside.get(conditionKey) ?? false;
        if (inside && !wasInside) {
            const currentCount = this.nearEntryCounts.get(conditionKey) ?? 0;
            this.nearEntryCounts.set(conditionKey, currentCount + 1);
        }
        this.nearWasInside.set(conditionKey, inside);

        return inside && (this.nearEntryCounts.get(conditionKey) ?? 0) >= count;
    }

    private evaluateNearDurationAtPosition(
        x: number,
        y: number,
        cond: Condition,
        conditionKey: string,
        deltaSeconds: number
    ): boolean {
        const dx = x - cond.x!;
        const dy = y - cond.y!;
        const distSq = dx * dx + dy * dy;
        const inside = distSq <= cond.radius! * cond.radius!;
        const prev = this.nearHoldSeconds.get(conditionKey) ?? 0;
        const next = inside ? prev + deltaSeconds : 0;
        this.nearHoldSeconds.set(conditionKey, next);
        return inside && next >= (cond.duration ?? 0);
    }

    private evaluateStillCondition(
        cond: Condition,
        scene: GameScene,
        conditionKey: string,
        deltaSeconds: number
    ): boolean {
        const candy = this.getCandyPoint(cond.candyTarget, scene);
        if (!candy) {
            this.stillHoldSeconds.set(conditionKey, 0);
            this.stillLastPositions.delete(conditionKey);
            return false;
        }

        const x = candy.pos.x;
        const y = candy.pos.y;
        const last = this.stillLastPositions.get(conditionKey);
        this.stillLastPositions.set(conditionKey, { x, y });
        if (!last) {
            this.stillHoldSeconds.set(conditionKey, 0);
            return false;
        }

        // Use final rendered physics positions; internal velocity can stay noisy under rope constraints.
        const vx = (x - last.x) / deltaSeconds;
        const vy = (y - last.y) / deltaSeconds;
        const threshold = cond.threshold ?? TextCommandController.DEFAULT_STILL_SPEED_THRESHOLD;
        const isStill = vx * vx + vy * vy <= threshold * threshold;
        const prev = this.stillHoldSeconds.get(conditionKey) ?? 0;
        const next = isStill ? prev + deltaSeconds : 0;
        this.stillHoldSeconds.set(conditionKey, next);
        return isStill && next >= (cond.duration ?? 0);
    }

    private evaluateCondition(
        cond: Condition,
        scene: GameScene,
        conditionKey: string,
        deltaSeconds: number
    ): boolean {
        const getGrab = () => {
            const index = cond.targetIndex;
            if (index === undefined) {
                return null;
            }
            return scene.bungees[index] ?? null;
        };
        const getCandy = () => this.getCandyPoint(cond.candyTarget, scene);
        const getObjectPos = () =>
            this.getTrackablePosition(cond.objectKind, cond.targetIndex, scene);

        switch (cond.type) {
            case "none":
                return true;
            case "and": {
                const results = (cond.conditions ?? []).map((child, index) =>
                    this.evaluateCondition(child, scene, `${conditionKey}.${index}`, deltaSeconds)
                );
                return results.length > 0 && results.every(Boolean);
            }
            case "or": {
                const results = (cond.conditions ?? []).map((child, index) =>
                    this.evaluateCondition(child, scene, `${conditionKey}.${index}`, deltaSeconds)
                );
                return results.some(Boolean);
            }

            case "candy_y_gt":
                return (getCandy()?.pos.y ?? Number.NEGATIVE_INFINITY) > cond.value!;

            case "candy_y_lt":
                return (getCandy()?.pos.y ?? Number.POSITIVE_INFINITY) < cond.value!;

            case "candy_x_gt":
                return (getCandy()?.pos.x ?? Number.NEGATIVE_INFINITY) > cond.value!;

            case "candy_x_lt":
                return (getCandy()?.pos.x ?? Number.POSITIVE_INFINITY) < cond.value!;

            case "grab_x_gt": {
                const grab = getGrab();
                return grab ? grab.x > cond.value! : false;
            }

            case "grab_x_lt": {
                const grab = getGrab();
                return grab ? grab.x < cond.value! : false;
            }

            case "grab_y_gt": {
                const grab = getGrab();
                return grab ? grab.y > cond.value! : false;
            }

            case "grab_y_lt": {
                const grab = getGrab();
                return grab ? grab.y < cond.value! : false;
            }

            case "obj_x_gt": {
                const pos = getObjectPos();
                return pos ? pos.x > cond.value! : false;
            }

            case "obj_x_lt": {
                const pos = getObjectPos();
                return pos ? pos.x < cond.value! : false;
            }

            case "obj_y_gt": {
                const pos = getObjectPos();
                return pos ? pos.y > cond.value! : false;
            }

            case "obj_y_lt": {
                const pos = getObjectPos();
                return pos ? pos.y < cond.value! : false;
            }

            case "candy_near": {
                const candy = getCandy();
                if (!candy) {
                    return false;
                }
                return this.evaluateNearConditionAtPosition(
                    candy.pos.x,
                    candy.pos.y,
                    cond,
                    conditionKey
                );
            }
            case "candy_near_for": {
                const candy = getCandy();
                if (!candy) {
                    this.nearHoldSeconds.set(conditionKey, 0);
                    return false;
                }
                return this.evaluateNearDurationAtPosition(
                    candy.pos.x,
                    candy.pos.y,
                    cond,
                    conditionKey,
                    deltaSeconds
                );
            }
            case "candy_still_for":
                return this.evaluateStillCondition(cond, scene, conditionKey, deltaSeconds);
            case "grab_near": {
                const grab = getGrab();
                if (!grab) {
                    return false;
                }
                return this.evaluateNearConditionAtPosition(grab.x, grab.y, cond, conditionKey);
            }
            case "grab_near_for": {
                const grab = getGrab();
                if (!grab) {
                    this.nearHoldSeconds.set(conditionKey, 0);
                    return false;
                }
                return this.evaluateNearDurationAtPosition(
                    grab.x,
                    grab.y,
                    cond,
                    conditionKey,
                    deltaSeconds
                );
            }
            case "obj_near": {
                const pos = getObjectPos();
                if (!pos) {
                    return false;
                }
                return this.evaluateNearConditionAtPosition(pos.x, pos.y, cond, conditionKey);
            }
            case "obj_near_for": {
                const pos = getObjectPos();
                if (!pos) {
                    this.nearHoldSeconds.set(conditionKey, 0);
                    return false;
                }
                return this.evaluateNearDurationAtPosition(
                    pos.x,
                    pos.y,
                    cond,
                    conditionKey,
                    deltaSeconds
                );
            }

            case "rope_cut":
                return this.cutRopes.has(cond.value!);

            case "no_rope":
                return scene.attachCount === 0;

            case "wait_frames":
                return (
                    this.frameCounter -
                    (this.waitStartFrames.get(conditionKey) ?? this.frameCounter)
                ) >= cond.value!;

            case "candy_vy_gt":
                return (getCandy()?.v.y ?? Number.NEGATIVE_INFINITY) > cond.value!;

            case "candy_vy_lt":
                return (getCandy()?.v.y ?? Number.POSITIVE_INFINITY) < cond.value!;
            case "candy_in_bubble":
                return this.isCandyInBubble(cond.candyTarget, scene);
            case "candy_in_lantern":
                return scene.isCandyInLantern;
            case "lantern_has_candy":
                return this.lanternHasCandy(cond.targetIndex, scene);
            case "mouse_has_candy":
                return Boolean(scene.miceManager?.activeMouseHasCandy());

            default:
                return false;
        }
    }

    private tickRepeatedPumpCommand(cmd: Command, scene: GameScene, deltaSeconds: number): void {
        const commandIndex = this.currentIndex;
        const whenKey = this.getConditionKey(commandIndex);

        if (cmd.status !== "running") {
            if (!this.evaluateCondition(cmd.condition, scene, whenKey, deltaSeconds)) {
                return;
            }

            cmd.status = "running";
            this.pumpClicksPerformed.set(commandIndex, 0);
            this.pumpNextClickAt.set(commandIndex, this.elapsedSeconds);

            if (cmd.untilCondition) {
                this.resetConditionStateForCommand(commandIndex, cmd.untilCondition, "until");
            }
            this.notifyChange();
        }

        const untilCondition = cmd.untilCondition;
        if (untilCondition) {
            const untilKey = this.getConditionKey(commandIndex, "until");
            if (this.evaluateCondition(untilCondition, scene, untilKey, deltaSeconds)) {
                cmd.status = "done";
                this.advanceToNextCommand();
                this.notifyChange();
                return;
            }
        }

        const clicksPerformed = this.pumpClicksPerformed.get(commandIndex) ?? 0;
        if (cmd.repeatCount !== undefined && clicksPerformed >= cmd.repeatCount) {
            cmd.status = "done";
            this.advanceToNextCommand();
            this.notifyChange();
            return;
        }

        const nextClickAt = this.pumpNextClickAt.get(commandIndex) ?? this.elapsedSeconds;
        if (this.elapsedSeconds + 1e-9 < nextClickAt) {
            return;
        }

        this.doActivatePump(cmd.targetIndex, scene, deltaSeconds);

        const performedAfterClick = clicksPerformed + 1;
        this.pumpClicksPerformed.set(commandIndex, performedAfterClick);
        this.pumpNextClickAt.set(commandIndex, this.elapsedSeconds + (cmd.repeatInterval ?? PUMP_TIMEOUT));

        if (cmd.repeatCount !== undefined && performedAfterClick >= cmd.repeatCount) {
            cmd.status = "done";
            this.advanceToNextCommand();
            this.notifyChange();
        }
    }

    private tickActiveCircleRotations(scene: GameScene, deltaSeconds: number): void {
        if (this.activeCircleRotations.size === 0) {
            return;
        }

        const degreesPerTick = TextCommandController.CIRCLE_ROTATION_SPEED_DEG * deltaSeconds;
        if (!Number.isFinite(degreesPerTick) || degreesPerTick === 0) {
            return;
        }

        for (const [index, direction] of this.activeCircleRotations) {
            const applied = this.applyCircleRotation(index, degreesPerTick * direction, scene);
            if (!applied) {
                this.activeCircleRotations.delete(index);
            }
        }
    }

    private tickActiveWheelRotations(scene: GameScene, deltaSeconds: number): void {
        if (this.activeWheelRotations.size === 0) {
            return;
        }

        const degreesPerTick = TextCommandController.WHEEL_ROTATION_SPEED_DEG * deltaSeconds;
        if (!Number.isFinite(degreesPerTick) || degreesPerTick === 0) {
            return;
        }

        for (const [index, direction] of this.activeWheelRotations) {
            const applied = this.applyWheelRotation(index, degreesPerTick * direction, scene);
            if (!applied) {
                this.activeWheelRotations.delete(index);
            }
        }
    }

    private executeAction(cmd: Command, scene: GameScene, deltaSeconds = 1 / 60): void {
        switch (cmd.action) {
            case "cut_rope":
                for (const index of cmd.targetIndices ?? [cmd.targetIndex]) {
                    this.doCutRope(index, scene);
                }
                break;
            case "pop_bubble":
                if (cmd.targetIndex >= 0) {
                    this.doPopFreeBubble(cmd.targetIndex, scene);
                } else {
                    this.doPopBubble(scene);
                }
                break;
            case "pop_bubble_left":
                this.doPopBubbleLeft(scene);
                break;
            case "pop_bubble_right":
                this.doPopBubbleRight(scene);
                break;
            case "pop_lightbulb_bubble":
                this.doPopLightBulbBubble(cmd.targetIndex, scene);
                break;
            case "toggle_gravity":
                this.doToggleGravity(scene);
                break;
            case "activate_pump":
                this.doActivatePump(cmd.targetIndex, scene, deltaSeconds);
                break;
            case "fire_gun":
                this.doFireGun(cmd.targetIndex, scene);
                break;
            case "tap_ghost":
                this.doTapGhost(cmd.targetIndex, scene);
                break;
            case "toggle_steam_tube":
                this.doToggleSteamTube(cmd.targetIndex, scene);
                break;
            case "release_lantern":
                this.doReleaseLantern(cmd.targetIndex, scene);
                break;
            case "rotate_circle":
                if (!cmd.direction) {
                    console.warn(
                        `[TextCmd] rotate_circle now requires an explicit direction (cw or ccw)`
                    );
                } else if (cmd.value !== undefined) {
                    const signedDegrees = cmd.direction === "cw" ? cmd.value : -cmd.value;
                    this.doRotateCircle(cmd.targetIndex, signedDegrees, scene);
                } else {
                    this.startRotateCircle(cmd.targetIndex, cmd.direction, scene);
                }
                break;
            case "stop_rotate_circle":
                this.stopRotateCircle(cmd.targetIndex, scene);
                break;
            case "rotate_wheel":
                if (!cmd.wheelMode) {
                    console.warn(
                        `[TextCmd] rotate_wheel now requires an explicit mode (extend or shorten)`
                    );
                } else {
                    this.startRotateWheel(cmd.targetIndex, cmd.wheelMode, scene);
                }
                break;
            case "stop_rotate_wheel":
                this.stopRotateWheel(cmd.targetIndex, scene);
                break;
            case "move_grab":
                this.doMoveGrab(cmd.targetIndex, cmd.value, cmd.value2, scene);
                break;
            case "kick_rope":
                this.doKickRope(cmd.targetIndex, scene);
                break;
            case "tap_mouse":
                this.doTapMouse(scene);
                break;
            case "drag_conveyor":
                this.doDragConveyor(cmd.targetIndex, cmd.value ?? 0, scene);
                break;
        }
    }

    private doCutRope(index: number, scene: GameScene): void {
        const grab = scene.bungees[index];
        if (!grab) {
            console.warn(`[TextCmd] No rope at index ${index}`);
            return;
        }

        const rope = grab.rope;
        if (!rope || rope.cut !== Constants.UNDEFINED) {
            console.warn(`[TextCmd] Rope ${index} already cut or missing`);
            return;
        }

        // Cut at the middle segment
        const midPart = Math.max(0, Math.floor((rope.parts.length - 1) / 2));
        SoundMgr.playSound(ResourceId.SND_ROPE_BLEAK_1 + rope.relaxed);
        rope.setCut(midPart);
        scene.detachCandy();

        this.cutRopes.add(index);
        console.log(`[TextCmd] Cut rope ${index} at segment ${midPart}`);
    }

    private doPopBubble(scene: GameScene): void {
        if (scene.candyBubble) {
            scene.popCandyBubble(false);
            console.log("[TextCmd] Popped candy bubble");
        } else if (scene.candyBubbleL) {
            scene.popCandyBubble(true);
            console.log("[TextCmd] Popped left candy bubble");
        } else if (scene.candyBubbleR) {
            scene.popCandyBubble(false);
            console.log("[TextCmd] Popped right candy bubble");
        } else {
            console.warn("[TextCmd] No candy bubble to pop");
        }
    }

    private doPopFreeBubble(index: number, scene: GameScene): void {
        const binding = this.getBubbleRuntimeBinding(index, scene);
        if (!binding) {
            console.warn(`[TextCmd] No active bubble at index ${index}`);
            return;
        }

        const { bubble } = binding;
        switch (binding.kind) {
            case "main":
                scene.popCandyBubble(false);
                console.log(`[TextCmd] Popped bubble ${index} attached to main candy`);
                return;
            case "left":
                scene.popCandyBubble(true);
                console.log(`[TextCmd] Popped bubble ${index} attached to left candy`);
                return;
            case "right":
                scene.popCandyBubble(false);
                console.log(`[TextCmd] Popped bubble ${index} attached to right candy`);
                return;
            case "lightbulb":
                if (binding.lightbulb) {
                    scene.popLightBulbBubble(binding.lightbulb);
                    console.log(`[TextCmd] Popped bubble ${index} captured by a lightbulb`);
                }
                return;
            case "free":
                break;
        }

        bubble.popped = true;
        bubble.removeChildWithID(0);
        scene.conveyors.remove(bubble);
        SoundMgr.playSound(ResourceId.SND_BUBBLE_BREAK);
        scene.bubbleDisappear.x = bubble.x;
        scene.bubbleDisappear.y = bubble.y;
        scene.bubbleDisappear.playTimeline(0);
        scene.aniPool.addChild(scene.bubbleDisappear);
        console.log(`[TextCmd] Popped free bubble ${index}`);
    }

    private doPopBubbleLeft(scene: GameScene): void {
        if (scene.candyBubbleL) {
            scene.popCandyBubble(true);
            console.log("[TextCmd] Popped left candy bubble");
            return;
        }
        if (scene.candyBubble && !scene.candyBubbleR) {
            scene.popCandyBubble(false);
            console.log("[TextCmd] Popped candy bubble");
            return;
        }
        console.warn("[TextCmd] No left candy bubble to pop");
    }

    private doPopBubbleRight(scene: GameScene): void {
        if (scene.candyBubbleR) {
            scene.popCandyBubble(false);
            console.log("[TextCmd] Popped right candy bubble");
            return;
        }
        if (scene.candyBubble && !scene.candyBubbleL) {
            scene.popCandyBubble(false);
            console.log("[TextCmd] Popped candy bubble");
            return;
        }
        console.warn("[TextCmd] No right candy bubble to pop");
    }

    private doPopLightBulbBubble(index: number, scene: GameScene): void {
        const bulb = scene.lightbulbs[index];
        if (!bulb) {
            console.warn(`[TextCmd] No lightbulb at index ${index}`);
            return;
        }
        if (!bulb.capturingBubble) {
            console.warn(`[TextCmd] Lightbulb ${index} has no bubble`);
            return;
        }
        scene.popLightBulbBubble(bulb);
        console.log(`[TextCmd] Popped lightbulb bubble ${index}`);
    }

    private doToggleGravity(scene: GameScene): void {
        Gravity.toggle();
        scene.gravityNormal = Gravity.isNormal();
        SoundMgr.playSound(
            scene.gravityNormal
                ? ResourceId.SND_GRAVITY_OFF
                : ResourceId.SND_GRAVITY_ON
        );

        // Toggle button visual if present
        if (scene.gravityButton) {
            scene.gravityButton.toggle();
        }

        console.log(
            `[TextCmd] Toggled gravity, now ${scene.gravityNormal ? "normal" : "inverted"}`
        );
    }

    private doActivatePump(index: number, scene: GameScene, deltaSeconds = 1 / 60): void {
        const pump = scene.pumps[index];
        if (!pump) {
            console.warn(`[TextCmd] No pump at index ${index}`);
            return;
        }

        const impulseDelta =
            Number.isFinite(deltaSeconds) && deltaSeconds > 0 ? deltaSeconds : 1 / 60;

        // Text commands run after the pump update system, so delayed touchTimer pumping can miss
        // the frame. Call the same engine API directly and clear the timer to avoid a double pump.
        pump.touchTimer = 0;
        pump.touch = -1;
        scene.operatePump(pump, impulseDelta);
        console.log(`[TextCmd] Activated pump ${index}`);
    }

    private doFireGun(index: number, scene: GameScene): void {
        const grab = scene.bungees[index];
        if (!grab || !grab.gun || grab.gunFired || grab.rope != null) {
            console.warn(`[TextCmd] Cannot fire gun at index ${index}`);
            return;
        }

        // Same logic as touchDown in touch.ts for gun firing
        const gunPos = { x: grab.x, y: grab.y };
        const starPos = scene.star.pos;
        const dx = gunPos.x - starPos.x;
        const dy = gunPos.y - starPos.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        const angle = Math.atan2(dy, dx);

        grab.gunFired = true;
        grab.gunInitialRotation = (angle * 180 / Math.PI) + 90;

        const ropeLength = Math.max(dist - 81, 81);

        const bungee = new Bungee(
            null,
            grab.x,
            grab.y,
            scene.star,
            scene.star.pos.x,
            scene.star.pos.y,
            ropeLength
        );
        bungee.bungeeAnchor.pin.copyFrom(bungee.bungeeAnchor.pos);
        grab.setRope(bungee);
        SoundMgr.playSound(ResourceId.SND_EXP_GUN);
        console.log(`[TextCmd] Fired gun ${index}`);
    }

    private doTapGhost(index: number, scene: GameScene): void {
        const ghost = scene.ghosts[index];
        if (!ghost) {
            console.warn(`[TextCmd] No ghost at index ${index}`);
            return;
        }
        ghost.onTouchDown(ghost.x, ghost.y);
        console.log(`[TextCmd] Tapped ghost ${index}`);
    }

    private doToggleSteamTube(index: number, scene: GameScene): void {
        const tube = scene.tubes[index];
        if (!tube) {
            console.warn(`[TextCmd] No steam tube at index ${index}`);
            return;
        }

        const valvePos = tube.getValveWorldPosition();
        tube.onTouchDown(valvePos.x, valvePos.y);
        console.log(`[TextCmd] Toggled steam tube ${index}`);
    }

    private doReleaseLantern(index: number, scene: GameScene): void {
        const lantern = scene.lanterns[index];
        if (!lantern) {
            console.warn(`[TextCmd] No lantern at index ${index}`);
            return;
        }
        lantern.onTouchDown(lantern.x, lantern.y);
        console.log(`[TextCmd] Tapped lantern ${index}`);
    }

    private startRotateCircle(index: number, direction: "cw" | "ccw", scene: GameScene): void {
        if (!scene.rotatedCircles[index]) {
            console.warn(`[TextCmd] No rotated circle at index ${index}`);
            return;
        }

        this.activeCircleRotations.set(index, direction === "cw" ? 1 : -1);
        console.log(`[TextCmd] Started rotating circle ${index} ${direction}`);
    }

    private stopRotateCircle(index: number, scene: GameScene): void {
        if (!scene.rotatedCircles[index]) {
            console.warn(`[TextCmd] No rotated circle at index ${index}`);
            return;
        }

        if (!this.activeCircleRotations.has(index)) {
            console.warn(`[TextCmd] Circle ${index} is not rotating`);
            return;
        }

        this.activeCircleRotations.delete(index);
        console.log(`[TextCmd] Stopped rotating circle ${index}`);
    }

    private applyCircleRotation(index: number, degrees: number, scene: GameScene): boolean {
        const circle = scene.rotatedCircles[index];
        if (!circle) {
            console.warn(`[TextCmd] No rotated circle at index ${index}`);
            return false;
        }
        if (!degrees) {
            return true;
        }

        const radians = Radians.fromDegrees(degrees);
        circle.rotation += degrees;

        if (circle.handle1) {
            circle.handle1.rotateAround(radians, circle.x, circle.y);
        }
        if (circle.handle2) {
            circle.handle2.rotateAround(radians, circle.x, circle.y);
        }

        const bungeeRadius = circle.sizeInPixels + 5 * scene.PM;
        const bubbleRadius = circle.sizeInPixels + 10 * scene.PM;

        for (const grab of scene.bungees) {
            if (!grab) {
                continue;
            }
            if (Vector.distance(grab.x, grab.y, circle.x, circle.y) <= bungeeRadius) {
                const pos = new Vector(grab.x, grab.y);
                pos.rotateAround(radians, circle.x, circle.y);
                grab.x = pos.x;
                grab.y = pos.y;
                if (grab.rope) {
                    grab.rope.bungeeAnchor.pos.copyFrom(pos);
                    grab.rope.bungeeAnchor.pin.copyFrom(pos);
                }
            }
        }

        for (const pump of scene.pumps) {
            if (!pump) {
                continue;
            }
            if (Vector.distance(pump.x, pump.y, circle.x, circle.y) <= bungeeRadius) {
                const pos = new Vector(pump.x, pump.y);
                pos.rotateAround(radians, circle.x, circle.y);
                pump.x = pos.x;
                pump.y = pos.y;
                pump.rotation += degrees;
                pump.updateRotation();
            }
        }

        for (const bubble of scene.bubbles) {
            if (!bubble) {
                continue;
            }
            if (bubble === scene.candyBubble || bubble === scene.candyBubbleL || bubble === scene.candyBubbleR) {
                continue;
            }
            if (Vector.distance(bubble.x, bubble.y, circle.x, circle.y) <= bubbleRadius) {
                const pos = new Vector(bubble.x, bubble.y);
                pos.rotateAround(radians, circle.x, circle.y);
                bubble.x = pos.x;
                bubble.y = pos.y;
            }
        }

        if (
            Rectangle.pointInRect(
                scene.target.x,
                scene.target.y,
                circle.x - circle.size,
                circle.y - circle.size,
                circle.size * 2,
                circle.size * 2
            )
        ) {
            const pos = new Vector(scene.target.x, scene.target.y);
            pos.rotateAround(radians, circle.x, circle.y);
            scene.target.x = pos.x;
            scene.target.y = pos.y;
        }

        return true;
    }

    private doRotateCircle(index: number, degrees: number, scene: GameScene): void {
        if (!degrees) {
            return;
        }
        this.applyCircleRotation(index, degrees, scene);
        console.log(`[TextCmd] Rotated circle ${index} by ${degrees} degrees`);
    }

    private startRotateWheel(index: number, mode: "extend" | "shorten", scene: GameScene): void {
        const grab = scene.bungees[index];
        if (!grab || !grab.wheel || !grab.rope) {
            console.warn(`[TextCmd] No wheel rope at index ${index}`);
            return;
        }

        this.activeWheelRotations.set(index, mode === "extend" ? 1 : -1);
        console.log(`[TextCmd] Started rotating wheel ${index} in ${mode} mode`);
    }

    private stopRotateWheel(index: number, scene: GameScene): void {
        const grab = scene.bungees[index];
        if (!grab || !grab.wheel || !grab.rope) {
            console.warn(`[TextCmd] No wheel rope at index ${index}`);
            return;
        }

        if (!this.activeWheelRotations.has(index)) {
            console.warn(`[TextCmd] Wheel ${index} is not rotating`);
            return;
        }

        this.activeWheelRotations.delete(index);
        console.log(`[TextCmd] Stopped rotating wheel ${index}`);
    }

    private applyWheelRotation(index: number, degrees: number, scene: GameScene): boolean {
        const grab = scene.bungees[index];
        if (!grab || !grab.wheel || !grab.rope) {
            console.warn(`[TextCmd] No wheel rope at index ${index}`);
            return false;
        }
        if (!degrees) {
            return true;
        }

        const center = new Vector(grab.x, grab.y);
        const radius = Math.max(1, scene.PM * 20);
        const start = new Vector(center.x + radius, center.y);
        const rad = Radians.fromDegrees(degrees);
        const end = new Vector(center.x + radius * Math.cos(rad), center.y + radius * Math.sin(rad));
        grab.handleWheelTouch(start.x, start.y);
        grab.handleWheelRotate(end);
        return true;
    }

    private doRotateWheel(index: number, degrees: number, scene: GameScene): void {
        if (!degrees) {
            return;
        }
        this.applyWheelRotation(index, degrees, scene);
        console.log(`[TextCmd] Rotated wheel ${index} by ${degrees} degrees`);
    }

    private doMoveGrab(
        index: number,
        value: number | undefined,
        value2: number | undefined,
        scene: GameScene
    ): void {
        const grab = scene.bungees[index];
        if (!grab || grab.moveLength <= 0) {
            console.warn(`[TextCmd] No movable grab at index ${index}`);
            return;
        }
        if (value === undefined || Number.isNaN(value)) {
            console.warn(`[TextCmd] move_grab requires a position value`);
            return;
        }

        if (grab.moveVertical) {
            const targetY = value2 ?? value;
            grab.y = MathHelper.fitToBoundaries(targetY, grab.minMoveValue, grab.maxMoveValue);
        } else {
            grab.x = MathHelper.fitToBoundaries(value, grab.minMoveValue, grab.maxMoveValue);
        }

        if (grab.rope) {
            const ba = grab.rope.bungeeAnchor;
            ba.pos.x = ba.pin.x = grab.x;
            ba.pos.y = ba.pin.y = grab.y;
        }
        console.log(`[TextCmd] Moved grab ${index}`);
    }

    private doKickRope(index: number, scene: GameScene): void {
        const grab = scene.bungees[index];
        if (!grab || !grab.kickable || !grab.rope) {
            console.warn(`[TextCmd] No kickable rope at index ${index}`);
            return;
        }
        if (grab.kicked) {
            console.warn(`[TextCmd] Rope ${index} already kicked`);
            return;
        }

        grab.rope.bungeeAnchor.pin.x = Constants.UNDEFINED;
        grab.rope.bungeeAnchor.pin.y = Constants.UNDEFINED;
        grab.rope.bungeeAnchor.setWeight(0.1);
        grab.kicked = true;
        grab.stickTimer = Constants.UNDEFINED;
        grab.kickActive = false;
        grab.updateKickState();
        SoundMgr.playSound(ResourceId.SND_EXP_SUCKER_DROP);
        console.log(`[TextCmd] Kicked rope ${index}`);
    }

    private doTapMouse(scene: GameScene): void {
        const mouse = scene.miceManager?.activeMouse;
        if (!mouse) {
            console.warn("[TextCmd] No active mouse");
            return;
        }
        scene.miceManager?.handleClick(mouse.x, mouse.y);
        console.log("[TextCmd] Tapped mouse");
    }

    private doDragConveyor(index: number, distance: number, scene: GameScene): void {
        const belts = Array.from(scene.conveyors.iterator());
        const belt = belts[index];
        if (!belt) {
            console.warn(`[TextCmd] No conveyor at index ${index}`);
            return;
        }
        if (!belt.isManual) {
            console.warn(`[TextCmd] Conveyor ${index} is not manual`);
            return;
        }

        const start = new Vector(
            belt.x + belt.direction.x * (belt.width * 0.5),
            belt.y + belt.direction.y * (belt.width * 0.5)
        );
        const end = new Vector(start.x + belt.direction.x * distance, start.y + belt.direction.y * distance);
        const pointerId = 0;

        belt.onPointerDown(start.x, start.y, pointerId);
        belt.onPointerMove(end.x, end.y, pointerId);
        belt.onPointerUp(end.x, end.y, pointerId);
        console.log(`[TextCmd] Dragged conveyor ${index} by ${distance}`);
    }

    private resetConditionStateForCommand(
        commandIndex: number,
        condition: Condition,
        phase: "when" | "until" = "when",
        path = ""
    ): void {
        const key = this.getConditionKey(commandIndex, phase, path);

        if (condition.type === "and" || condition.type === "or") {
            this.nearEntryCounts.delete(key);
            this.nearWasInside.delete(key);
            this.nearHoldSeconds.delete(key);
            this.stillHoldSeconds.delete(key);
            this.stillLastPositions.delete(key);
            this.waitStartFrames.delete(key);

            for (const [index, child] of (condition.conditions ?? []).entries()) {
                this.resetConditionStateForCommand(commandIndex, child, phase, `${path}.${index}`);
            }
            return;
        }

        this.nearEntryCounts.delete(key);
        this.nearWasInside.delete(key);
        this.nearHoldSeconds.delete(key);
        this.stillHoldSeconds.delete(key);
        this.stillLastPositions.delete(key);
        this.waitStartFrames.delete(key);

        if (
            (condition.type === "candy_near" ||
                condition.type === "grab_near" ||
                condition.type === "obj_near") &&
            (condition.count ?? 1) > 1
        ) {
            this.nearEntryCounts.set(key, 0);
            this.nearWasInside.set(key, false);
        }
        if (
            condition.type === "candy_near_for" ||
            condition.type === "grab_near_for" ||
            condition.type === "obj_near_for"
        ) {
            this.nearHoldSeconds.set(key, 0);
        }
        if (condition.type === "candy_still_for") {
            this.stillHoldSeconds.set(key, 0);
        }
        if (condition.type === "wait_frames") {
            this.waitStartFrames.set(key, this.frameCounter);
        }
    }

    private advanceToNextCommand(): void {
        const finishedIndex = this.currentIndex;
        const finishedCmd = this.commands[finishedIndex];
        if (finishedCmd) {
            this.clearConditionStateForCommand(finishedIndex, finishedCmd.condition, "when");
            if (finishedCmd.untilCondition) {
                this.clearConditionStateForCommand(finishedIndex, finishedCmd.untilCondition, "until");
            }
        }
        this.pumpClicksPerformed.delete(finishedIndex);
        this.pumpNextClickAt.delete(finishedIndex);
        this.currentIndex++;

        if (this.currentIndex < this.commands.length) {
            const nextCmd = this.commands[this.currentIndex]!;
            nextCmd.status = "waiting";
            this.resetConditionStateForCommand(this.currentIndex, nextCmd.condition);
        } else {
            this._status = "finished";
        }
    }

    private isRepeatedPumpCommand(cmd: Command): boolean {
        return cmd.action === "activate_pump" &&
            (cmd.repeatCount !== undefined || cmd.untilCondition !== undefined);
    }

    private clearConditionStateForCommand(
        commandIndex: number,
        condition: Condition,
        phase: "when" | "until" = "when",
        path = ""
    ): void {
        const key = this.getConditionKey(commandIndex, phase, path);
        this.nearEntryCounts.delete(key);
        this.nearWasInside.delete(key);
        this.nearHoldSeconds.delete(key);
        this.stillHoldSeconds.delete(key);
        this.stillLastPositions.delete(key);
        this.waitStartFrames.delete(key);

        if (condition.type === "and" || condition.type === "or") {
            for (const [index, child] of (condition.conditions ?? []).entries()) {
                this.clearConditionStateForCommand(commandIndex, child, phase, `${path}.${index}`);
            }
        }
    }

    private getConditionKey(
        commandIndex: number,
        phase: "when" | "until" = "when",
        path = ""
    ): string {
        return `${commandIndex}:${phase}${path}`;
    }

    private notifyChange(): void {
        if (this._onStatusChange) {
            this._onStatusChange();
        }
    }
}

// Singleton instance
const textCommandController = new TextCommandController();
export default textCommandController;
