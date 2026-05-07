import resolution from "@/resolution";

const GRID_SIZE = 100;
const GRID_COLOR = "rgba(255, 255, 255, 0.12)";
const AXIS_COLOR = "rgba(255, 255, 255, 0.3)";
const LABEL_COLOR = "rgba(255, 255, 255, 0.5)";
const LABEL_FONT = "22px 'Cascadia Code', 'Fira Code', 'Consolas', monospace";
const LABEL_PADDING = 8;

class GridOverlay {
    private canvas: HTMLCanvasElement | null = null;
    private ctx: CanvasRenderingContext2D | null = null;

    domReady(): void {
        if (this.canvas) {
            return;
        }

        const gameArea = document.getElementById("gameArea");
        if (!gameArea) {
            return;
        }

        const canvas = document.createElement("canvas");
        canvas.id = "gridOverlay";
        canvas.width = resolution.CANVAS_WIDTH;
        canvas.height = resolution.CANVAS_HEIGHT;
        canvas.style.position = "absolute";
        canvas.style.top = "0";
        canvas.style.left = "0";
        canvas.style.pointerEvents = "none";
        canvas.style.zIndex = "90";

        gameArea.appendChild(canvas);

        this.canvas = canvas;
        this.ctx = canvas.getContext("2d");

        this.updateCanvasSize();
        window.addEventListener("resize", () => this.updateCanvasSize());
    }

    private updateCanvasSize(): void {
        if (!this.canvas) {
            return;
        }

        const width = resolution.CANVAS_WIDTH;
        const height = resolution.CANVAS_HEIGHT;

        if (this.canvas.width !== width || this.canvas.height !== height) {
            this.canvas.width = width;
            this.canvas.height = height;
        }

        this.canvas.style.width = `${width}px`;
        this.canvas.style.height = `${height}px`;

        this.drawGrid();
    }

    private drawGrid(): void {
        if (!this.canvas || !this.ctx) {
            return;
        }

        const ctx = this.ctx;
        const width = this.canvas.width;
        const height = this.canvas.height;

        ctx.clearRect(0, 0, width, height);

        ctx.lineWidth = 1;
        ctx.strokeStyle = GRID_COLOR;
        ctx.beginPath();
        for (let x = 0; x <= width; x += GRID_SIZE) {
            ctx.moveTo(x + 0.5, 0);
            ctx.lineTo(x + 0.5, height);
        }
        for (let y = 0; y <= height; y += GRID_SIZE) {
            ctx.moveTo(0, y + 0.5);
            ctx.lineTo(width, y + 0.5);
        }
        ctx.stroke();

        ctx.strokeStyle = AXIS_COLOR;
        ctx.beginPath();
        ctx.moveTo(0.5, 0);
        ctx.lineTo(0.5, height);
        ctx.moveTo(0, 0.5);
        ctx.lineTo(width, 0.5);
        ctx.stroke();

        ctx.fillStyle = LABEL_COLOR;
        ctx.font = LABEL_FONT;
        ctx.textBaseline = "top";
        ctx.textAlign = "left";

        for (let x = 0; x <= width; x += GRID_SIZE) {
            ctx.fillText(`${x}`, x + LABEL_PADDING, LABEL_PADDING);
        }

        ctx.textBaseline = "top";
        ctx.textAlign = "left";
        for (let y = 0; y <= height; y += GRID_SIZE) {
            ctx.fillText(`${y}`, LABEL_PADDING, y + LABEL_PADDING);
        }
    }
}

export default new GridOverlay();
