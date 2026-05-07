interface PointerCaptureSettings {
    element: HTMLElement;
    positionElement?: HTMLElement;
    getZoom?: () => number;
    shouldHandleEvent?: (event: Event) => boolean;
    onStart?: (x: number, y: number) => void;
    onMove?: (x: number, y: number) => void;
    onEnd?: (x: number, y: number) => void;
    onOut?: (x: number, y: number) => void;
}

/**
 * Captures and normalizes pointer events using the modern Pointer Events API
 */
class PointerCapture {
    static readonly startEventName = "pointerdown";
    static readonly endEventName = "pointerup";

    el: HTMLElement;
    positionElement: HTMLElement;
    getZoom: (() => number) | undefined;
    shouldHandleEvent: ((event: Event) => boolean) | undefined;
    activePointerId: number | null;
    mouseActive: boolean;
    lastPointerMouseEventTs: number;
    startHandler: (event: PointerEvent) => void;
    moveHandler: (event: PointerEvent) => void;
    endHandler: (event: PointerEvent) => void;
    cancelHandler: (event: PointerEvent) => void;
    mouseDownHandler: (event: MouseEvent) => void;
    mouseMoveHandler: (event: MouseEvent) => void;
    mouseUpHandler: (event: MouseEvent) => void;
    mouseLeaveHandler: (event: MouseEvent) => void;

    constructor(settings: PointerCaptureSettings) {
        this.el = settings.element;
        this.positionElement = settings.positionElement ?? settings.element;
        this.getZoom = settings.getZoom;
        this.shouldHandleEvent = settings.shouldHandleEvent;
        this.activePointerId = null;
        this.mouseActive = false;
        this.lastPointerMouseEventTs = 0;

        const shouldIgnoreMouseFallback = (): boolean =>
            Date.now() - this.lastPointerMouseEventTs < 100;

        const canHandle = (event: Event): boolean =>
            this.shouldHandleEvent ? this.shouldHandleEvent(event) : true;

        // Save references to the event handlers so they can be removed
        this.startHandler = (event: PointerEvent): void => {
            if (!canHandle(event)) {
                return;
            }
            event.preventDefault();

            if (event.pointerType === "mouse") {
                this.lastPointerMouseEventTs = Date.now();
            }

            // Only handle the first pointer
            if (this.activePointerId === null) {
                this.activePointerId = event.pointerId;
                this.el.setPointerCapture(event.pointerId);

                if (settings.onStart) {
                    this.translatePosition(event, settings.onStart);
                }
            }
        };

        this.moveHandler = (event: PointerEvent): void => {
            if (!canHandle(event)) {
                return;
            }

            if (event.pointerType === "mouse") {
                this.lastPointerMouseEventTs = Date.now();
            }

            // Always allow move events (for hover effects), but only prevent default
            // when actively dragging to allow normal scrolling when not interacting
            if (this.activePointerId !== null && event.pointerId === this.activePointerId) {
                event.preventDefault();
            }

            // Fire onMove for any pointer movement (hover or drag)
            if (settings.onMove) {
                this.translatePosition(event, settings.onMove);
            }
        };

        this.endHandler = (event: PointerEvent): void => {
            if (!canHandle(event)) {
                return;
            }
            event.preventDefault();

            if (event.pointerType === "mouse") {
                this.lastPointerMouseEventTs = Date.now();
            }

            if (event.pointerId === this.activePointerId) {
                this.activePointerId = null;

                if (settings.onEnd) {
                    this.translatePosition(event, settings.onEnd);
                }
            }
        };

        this.cancelHandler = (event: PointerEvent): void => {
            if (!canHandle(event)) {
                return;
            }

            if (event.pointerType === "mouse") {
                this.lastPointerMouseEventTs = Date.now();
            }

            if (event.pointerId === this.activePointerId) {
                this.activePointerId = null;

                if (settings.onOut) {
                    this.translatePosition(event, settings.onOut);
                }
            }
        };

        this.mouseDownHandler = (event: MouseEvent): void => {
            if (shouldIgnoreMouseFallback() || !canHandle(event)) {
                return;
            }
            event.preventDefault();
            this.mouseActive = true;
            if (settings.onStart) {
                this.translatePosition(event, settings.onStart);
            }
        };

        this.mouseMoveHandler = (event: MouseEvent): void => {
            if (shouldIgnoreMouseFallback() || !canHandle(event)) {
                return;
            }
            if (this.mouseActive) {
                event.preventDefault();
            }
            if (settings.onMove) {
                this.translatePosition(event, settings.onMove);
            }
        };

        this.mouseUpHandler = (event: MouseEvent): void => {
            if (shouldIgnoreMouseFallback() || !canHandle(event)) {
                return;
            }
            if (!this.mouseActive) {
                return;
            }
            event.preventDefault();
            this.mouseActive = false;
            if (settings.onEnd) {
                this.translatePosition(event, settings.onEnd);
            }
        };

        this.mouseLeaveHandler = (event: MouseEvent): void => {
            if (shouldIgnoreMouseFallback() || !canHandle(event)) {
                return;
            }
            if (!this.mouseActive) {
                return;
            }
            this.mouseActive = false;
            if (settings.onOut) {
                this.translatePosition(event, settings.onOut);
            }
        };
    }

    /**
     * Translates from page-relative to element-relative position
     */
    translatePosition(event: PointerEvent | MouseEvent, callback: (x: number, y: number) => void) {
        const rect = this.positionElement.getBoundingClientRect();
        const zoom = this.getZoom ? this.getZoom() : 1;

        // Use clientX/Y which are relative to the viewport, then adjust for element position
        const mouseX = Math.round((event.clientX - rect.left) / zoom);
        const mouseY = Math.round((event.clientY - rect.top) / zoom);

        callback(mouseX, mouseY);
    }

    /**
     * Activates pointer capture by attaching event listeners
     */
    activate() {
        this.el.addEventListener("pointerdown", this.startHandler);
        this.el.addEventListener("pointermove", this.moveHandler);
        this.el.addEventListener("pointerup", this.endHandler);
        this.el.addEventListener("pointercancel", this.cancelHandler);
        this.el.addEventListener("mousedown", this.mouseDownHandler);
        this.el.addEventListener("mousemove", this.mouseMoveHandler);
        this.el.addEventListener("mouseup", this.mouseUpHandler);
        this.el.addEventListener("mouseleave", this.mouseLeaveHandler);

        // Prevent touch actions to avoid browser handling
        this.el.style.touchAction = "none";
    }

    /**
     * Deactivates pointer capture by removing event listeners
     */
    deactivate() {
        this.el.removeEventListener("pointerdown", this.startHandler);
        this.el.removeEventListener("pointermove", this.moveHandler);
        this.el.removeEventListener("pointerup", this.endHandler);
        this.el.removeEventListener("pointercancel", this.cancelHandler);
        this.el.removeEventListener("mousedown", this.mouseDownHandler);
        this.el.removeEventListener("mousemove", this.mouseMoveHandler);
        this.el.removeEventListener("mouseup", this.mouseUpHandler);
        this.el.removeEventListener("mouseleave", this.mouseLeaveHandler);

        // Reset touch action
        this.el.style.touchAction = "";
    }
}

export default PointerCapture;
