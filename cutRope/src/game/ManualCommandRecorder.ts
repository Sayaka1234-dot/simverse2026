type CommandSink = (line: string) => void;

type CandySample = {
    elapsed: number;
    x: number;
    y: number;
};

type ManualRecordScene = {
    star?: {
        pos?: {
            x: number;
            y: number;
        } | null;
    } | null;
};

const MAX_HISTORY_SECONDS = 3;
const EARLY_ACTION_SECONDS = 0.2;
const QUICK_ACTION_SECONDS = 0.2;
const STILL_WINDOW_SECONDS = 0.3;
const STILL_RADIUS = 6;
const NEAR_RADIUS = 60;
const MOTION_MIN_DELTA = 20;
const GRID_STEP = 10;

function roundToStep(value: number, step: number): number {
    return Math.round(value / step) * step;
}

function floorToStep(value: number, step: number): number {
    return Math.floor(value / step) * step;
}

function ceilToStep(value: number, step: number): number {
    return Math.ceil(value / step) * step;
}

function distance(a: CandySample, b: CandySample): number {
    return Math.hypot(a.x - b.x, a.y - b.y);
}

export class ManualCommandRecorder {
    private commandSink: CommandSink | null = null;
    private samples: CandySample[] = [];
    private elapsed = 0;
    private lastActionAt: number | null = null;
    private actionCount = 0;

    setCommandSink(sink: CommandSink | null): void {
        this.commandSink = sink;
    }

    reset(): void {
        this.samples = [];
        this.elapsed = 0;
        this.lastActionAt = null;
        this.actionCount = 0;
    }

    tick(scene: ManualRecordScene, deltaSeconds: number): void {
        const delta = Number.isFinite(deltaSeconds) && deltaSeconds > 0 ? deltaSeconds : 0;
        this.elapsed += delta;
        this.captureSample(scene);
        this.pruneSamples();
    }

    recordCutRope(index: number, scene: ManualRecordScene): void {
        this.recordAction(`cut_rope ${index}`, scene);
    }

    recordPopBubble(index: number | null, scene: ManualRecordScene): void {
        const action = index !== null && index >= 0 ? `pop_bubble ${index}` : "pop_bubble";
        this.recordAction(action, scene);
    }

    recordPopBubbleLeft(scene: ManualRecordScene): void {
        this.recordAction("pop_bubble_left", scene);
    }

    recordPopBubbleRight(scene: ManualRecordScene): void {
        this.recordAction("pop_bubble_right", scene);
    }

    recordPopLightBulbBubble(index: number, scene: ManualRecordScene): void {
        this.recordAction(`pop_lightbulb_bubble ${index}`, scene);
    }

    recordActivatePump(index: number, scene: ManualRecordScene): void {
        this.recordAction(`activate_pump ${index}`, scene);
    }

    recordToggleGravity(scene: ManualRecordScene): void {
        this.recordAction("toggle_gravity", scene);
    }

    recordFireGun(index: number, scene: ManualRecordScene): void {
        this.recordAction(`fire_gun ${index}`, scene);
    }

    recordTapGhost(index: number, scene: ManualRecordScene): void {
        this.recordAction(`tap_ghost ${index}`, scene);
    }

    recordToggleSteamTube(index: number, scene: ManualRecordScene): void {
        this.recordAction(`toggle_steam_tube ${index}`, scene);
    }

    recordReleaseLantern(index: number, scene: ManualRecordScene): void {
        this.recordAction(`release_lantern ${index}`, scene);
    }

    recordKickRope(index: number, scene: ManualRecordScene): void {
        this.recordAction(`kick_rope ${index}`, scene);
    }

    recordTapMouse(scene: ManualRecordScene): void {
        this.recordAction("tap_mouse", scene);
    }

    private recordAction(actionText: string, scene: ManualRecordScene): void {
        this.captureSample(scene);
        const condition = this.inferCondition();
        const line = condition ? `${actionText} when ${condition}` : actionText;

        this.commandSink?.(line);
        this.lastActionAt = this.elapsed;
        this.actionCount++;
    }

    private inferCondition(): string | null {
        const current = this.samples[this.samples.length - 1];
        if (!current) {
            return null;
        }

        if (this.actionCount === 0 && this.elapsed <= EARLY_ACTION_SECONDS) {
            return null;
        }

        if (
            this.lastActionAt !== null &&
            this.elapsed - this.lastActionAt <= QUICK_ACTION_SECONDS
        ) {
            return null;
        }

        const stableCondition = this.inferStableCondition(current);
        if (stableCondition) {
            return stableCondition;
        }

        const motionCondition = this.inferMotionCondition(current);
        if (motionCondition) {
            return motionCondition;
        }

        return this.formatNearCondition(current);
    }

    private inferStableCondition(current: CandySample): string | null {
        const recent = this.samples.filter(
            (sample) => current.elapsed - sample.elapsed <= STILL_WINDOW_SECONDS
        );
        if (recent.length < 6) {
            return null;
        }

        const windowDuration = current.elapsed - recent[0]!.elapsed;
        if (windowDuration < STILL_WINDOW_SECONDS * 0.8) {
            return null;
        }

        const isStable = recent.every((sample) => distance(sample, current) <= STILL_RADIUS);
        if (!isStable) {
            return null;
        }

        return `candy_still for 0.3 and ${this.formatNearCondition(current)}`;
    }

    private inferMotionCondition(current: CandySample): string | null {
        const reference = this.samples.find(
            (sample) => current.elapsed - sample.elapsed >= STILL_WINDOW_SECONDS
        ) ?? this.samples[0];
        if (!reference) {
            return null;
        }

        const dx = current.x - reference.x;
        const dy = current.y - reference.y;

        if (Math.abs(dy) >= Math.abs(dx) && Math.abs(dy) >= MOTION_MIN_DELTA) {
            const threshold = dy > 0
                ? floorToStep(current.y, GRID_STEP)
                : ceilToStep(current.y, GRID_STEP);
            return `candy_y ${dy > 0 ? ">" : "<"} ${threshold}`;
        }

        if (Math.abs(dx) >= MOTION_MIN_DELTA) {
            const threshold = dx > 0
                ? floorToStep(current.x, GRID_STEP)
                : ceilToStep(current.x, GRID_STEP);
            return `candy_x ${dx > 0 ? ">" : "<"} ${threshold}`;
        }

        return null;
    }

    private formatNearCondition(sample: CandySample): string {
        const x = roundToStep(sample.x, GRID_STEP);
        const y = roundToStep(sample.y, GRID_STEP);
        return `candy_near ${x},${y},${NEAR_RADIUS}`;
    }

    private captureSample(scene: ManualRecordScene): void {
        const pos = scene.star?.pos;
        if (!pos || !Number.isFinite(pos.x) || !Number.isFinite(pos.y)) {
            return;
        }

        const last = this.samples[this.samples.length - 1];
        if (last && last.elapsed === this.elapsed) {
            last.x = pos.x;
            last.y = pos.y;
            return;
        }

        this.samples.push({
            elapsed: this.elapsed,
            x: pos.x,
            y: pos.y,
        });
    }

    private pruneSamples(): void {
        const minElapsed = this.elapsed - MAX_HISTORY_SECONDS;
        while (this.samples.length > 0 && this.samples[0]!.elapsed < minElapsed) {
            this.samples.shift();
        }
    }
}

const manualCommandRecorder = new ManualCommandRecorder();
export default manualCommandRecorder;
