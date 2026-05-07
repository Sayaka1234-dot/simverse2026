import LevelState from "@/game/LevelState";

const OVERLAY_ID = "levelFilenameOverlay";

class LevelFilenameOverlay {
    private element: HTMLDivElement | null = null;
    private lastFilename = "";
    private rafId: number | null = null;

    domReady(): void {
        if (this.element) {
            return;
        }

        const gameArea = document.getElementById("gameArea");
        if (!gameArea) {
            return;
        }

        if (window.getComputedStyle(gameArea).position === "static") {
            gameArea.style.position = "relative";
        }

        const element = document.createElement("div");
        element.id = OVERLAY_ID;
        element.setAttribute("aria-live", "polite");
        element.style.position = "absolute";
        element.style.left = "16px";
        element.style.bottom = "16px";
        element.style.zIndex = "160";
        element.style.pointerEvents = "none";
        element.style.padding = "6px 12px";
        element.style.borderRadius = "8px";
        element.style.background = "rgba(0, 0, 0, 0.46)";
        element.style.color = "rgba(255, 255, 255, 0.94)";
        element.style.font =
            "700 28px 'Cascadia Code', 'Fira Code', 'Consolas', monospace";
        element.style.letterSpacing = "0.04em";
        element.style.lineHeight = "1";
        element.style.textShadow = "0 2px 5px rgba(0, 0, 0, 0.85)";
        element.style.webkitTextStroke = "1px rgba(0, 0, 0, 0.4)";

        gameArea.appendChild(element);
        this.element = element;

        this.update();
    }

    private update(): void {
        const filename = this.getCurrentLevelFilename();
        if (filename !== this.lastFilename && this.element) {
            this.lastFilename = filename;
            this.element.textContent = filename;
            this.element.style.display = filename ? "block" : "none";
        }

        this.rafId = window.requestAnimationFrame(() => this.update());
    }

    private getCurrentLevelFilename(): string {
        const levelId = LevelState.loadedMap?.levelId;
        if (typeof levelId !== "string" || levelId.trim().length === 0) {
            return "";
        }

        const trimmedLevelId = levelId.trim();
        return trimmedLevelId.endsWith(".json") ? trimmedLevelId : `${trimmedLevelId}.json`;
    }

    destroy(): void {
        if (this.rafId !== null) {
            window.cancelAnimationFrame(this.rafId);
            this.rafId = null;
        }

        this.element?.remove();
        this.element = null;
        this.lastFilename = "";
    }
}

export default new LevelFilenameOverlay();
