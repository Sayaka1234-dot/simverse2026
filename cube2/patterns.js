/**
 * Pattern definitions for cube faces.
 * Supports rotation.
 */

const BASE_TEXT_FONT = '"Segoe UI", "Trebuchet MS", sans-serif';
const TEXT_COLORS = [
    '#FFE66D', '#A8E6CF', '#DDA0DD', '#87CEEB', '#F0E68C',
    '#FFB347', '#FF8A80', '#82B1FF', '#B9F6CA', '#FFCC80',
    '#E6EE9C', '#80DEEA', '#CE93D8', '#FFAB91', '#90CAF9',
    '#B39DDB', '#FFCDD2', '#C5E1A5', '#9FA8DA', '#80CBC4',
    '#FFECB3', '#F48FB1', '#A5D6A7', '#81D4FA', '#D1C4E9',
    '#FFCCBC', '#DCEDC8', '#CFD8DC', '#F8BBD0', '#B2EBF2',
    '#C8E6C9', '#FFF59D', '#EF9A9A', '#9CCC65', '#4DD0E1'
];

function createTextPattern(text, color, label = text, options = {}) {
    const {
        fontScale = 0.56,
        fontFamily = BASE_TEXT_FONT,
        fontWeight = 800,
        offsetY = 0.02
    } = options;

    return {
        label,
        color,
        draw(ctx, size) {
            ctx.fillStyle = color;
            ctx.font = `${fontWeight} ${size * fontScale}px ${fontFamily}`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(text, size / 2, size / 2 + size * offsetY);
        }
    };
}

function createCirclePattern(color, label) {
    return {
        label,
        color,
        draw(ctx, size) {
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(size / 2, size / 2, size * 0.27, 0, Math.PI * 2);
            ctx.fill();
        }
    };
}

function createSquarePattern(color, label) {
    return {
        label,
        color,
        draw(ctx, size) {
            const side = size * 0.54;
            const offset = (size - side) / 2;
            ctx.fillStyle = color;
            ctx.fillRect(offset, offset, side, side);
        }
    };
}

function createTrianglePattern(color, label) {
    return {
        label,
        color,
        draw(ctx, size) {
            const cx = size / 2;
            const top = size * 0.2;
            const bottom = size * 0.8;
            const halfBase = size * 0.24;
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.moveTo(cx, top);
            ctx.lineTo(cx + halfBase, bottom);
            ctx.lineTo(cx - halfBase, bottom);
            ctx.closePath();
            ctx.fill();
        }
    };
}

function createDiamondPattern(color, label) {
    return {
        label,
        color,
        draw(ctx, size) {
            const cx = size / 2;
            const cy = size / 2;
            const r = size * 0.3;
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.moveTo(cx, cy - r);
            ctx.lineTo(cx + r, cy);
            ctx.lineTo(cx, cy + r);
            ctx.lineTo(cx - r, cy);
            ctx.closePath();
            ctx.fill();
        }
    };
}

function createPlusPattern(color, label) {
    return {
        label,
        color,
        draw(ctx, size) {
            const thickness = size * 0.16;
            const length = size * 0.62;
            const cx = size / 2;
            const cy = size / 2;
            ctx.fillStyle = color;
            ctx.fillRect(cx - thickness / 2, cy - length / 2, thickness, length);
            ctx.fillRect(cx - length / 2, cy - thickness / 2, length, thickness);
        }
    };
}

function createNumberPatterns() {
    const patterns = {};
    Array.from({ length: 9 }, (_, index) => String(index + 1)).forEach((digit, index) => {
        patterns[digit] = createTextPattern(digit, TEXT_COLORS[index], digit);
    });
    return patterns;
}

function createLetterPatterns() {
    const patterns = {};
    'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('').forEach((letter, index) => {
        patterns[letter] = createTextPattern(letter, TEXT_COLORS[(index + 9) % TEXT_COLORS.length], letter);
    });
    return patterns;
}

const PATTERNS = {
    arrow_up: {
        label: 'Arrow Up',
        color: '#FF6B6B',
        draw(ctx, size) {
            const cx = size / 2;
            const cy = size / 2;
            const s = size * 0.35;
            ctx.fillStyle = this.color;
            ctx.beginPath();
            ctx.moveTo(cx, cy - s);
            ctx.lineTo(cx + s * 0.7, cy + s * 0.3);
            ctx.lineTo(cx + s * 0.25, cy + s * 0.3);
            ctx.lineTo(cx + s * 0.25, cy + s);
            ctx.lineTo(cx - s * 0.25, cy + s);
            ctx.lineTo(cx - s * 0.25, cy + s * 0.3);
            ctx.lineTo(cx - s * 0.7, cy + s * 0.3);
            ctx.closePath();
            ctx.fill();
        }
    },
    arrow_right: {
        label: 'Arrow Right',
        color: '#4ECDC4',
        draw(ctx, size) {
            const cx = size / 2;
            const cy = size / 2;
            const s = size * 0.35;
            ctx.fillStyle = this.color;
            ctx.beginPath();
            ctx.moveTo(cx + s, cy);
            ctx.lineTo(cx - s * 0.3, cy - s * 0.7);
            ctx.lineTo(cx - s * 0.3, cy - s * 0.25);
            ctx.lineTo(cx - s, cy - s * 0.25);
            ctx.lineTo(cx - s, cy + s * 0.25);
            ctx.lineTo(cx - s * 0.3, cy + s * 0.25);
            ctx.lineTo(cx - s * 0.3, cy + s * 0.7);
            ctx.closePath();
            ctx.fill();
        }
    },
    arrow_down: {
        label: 'Arrow Down',
        color: '#FF9F43',
        draw(ctx, size) {
            const cx = size / 2;
            const cy = size / 2;
            const s = size * 0.35;
            ctx.fillStyle = this.color;
            ctx.beginPath();
            ctx.moveTo(cx, cy + s);
            ctx.lineTo(cx + s * 0.7, cy - s * 0.3);
            ctx.lineTo(cx + s * 0.25, cy - s * 0.3);
            ctx.lineTo(cx + s * 0.25, cy - s);
            ctx.lineTo(cx - s * 0.25, cy - s);
            ctx.lineTo(cx - s * 0.25, cy - s * 0.3);
            ctx.lineTo(cx - s * 0.7, cy - s * 0.3);
            ctx.closePath();
            ctx.fill();
        }
    },
    arrow_left: {
        label: 'Arrow Left',
        color: '#5DADE2',
        draw(ctx, size) {
            const cx = size / 2;
            const cy = size / 2;
            const s = size * 0.35;
            ctx.fillStyle = this.color;
            ctx.beginPath();
            ctx.moveTo(cx - s, cy);
            ctx.lineTo(cx + s * 0.3, cy - s * 0.7);
            ctx.lineTo(cx + s * 0.3, cy - s * 0.25);
            ctx.lineTo(cx + s, cy - s * 0.25);
            ctx.lineTo(cx + s, cy + s * 0.25);
            ctx.lineTo(cx + s * 0.3, cy + s * 0.25);
            ctx.lineTo(cx + s * 0.3, cy + s * 0.7);
            ctx.closePath();
            ctx.fill();
        }
    },
    star: {
        label: 'Star',
        color: '#FFD700',
        draw(ctx, size) {
            const cx = size / 2;
            const cy = size / 2;
            const outerR = size * 0.33;
            const innerR = outerR * 0.4;
            ctx.fillStyle = this.color;
            ctx.beginPath();
            for (let i = 0; i < 5; i += 1) {
                const outerAngle = (i * 72 - 90) * Math.PI / 180;
                const innerAngle = (i * 72 - 54) * Math.PI / 180;
                if (i === 0) {
                    ctx.moveTo(cx + outerR * Math.cos(outerAngle), cy + outerR * Math.sin(outerAngle));
                } else {
                    ctx.lineTo(cx + outerR * Math.cos(outerAngle), cy + outerR * Math.sin(outerAngle));
                }
                ctx.lineTo(cx + innerR * Math.cos(innerAngle), cy + innerR * Math.sin(innerAngle));
            }
            ctx.closePath();
            ctx.fill();
        }
    },
    heart: {
        label: 'Heart',
        color: '#FF4757',
        draw(ctx, size) {
            const cx = size / 2;
            const cy = size / 2 + size * 0.04;
            const s = size * 0.3;
            ctx.fillStyle = this.color;
            ctx.beginPath();
            ctx.moveTo(cx, cy + s * 0.7);
            ctx.bezierCurveTo(cx - s * 1.5, cy - s * 0.3, cx - s * 0.5, cy - s * 1.3, cx, cy - s * 0.5);
            ctx.bezierCurveTo(cx + s * 0.5, cy - s * 1.3, cx + s * 1.5, cy - s * 0.3, cx, cy + s * 0.7);
            ctx.closePath();
            ctx.fill();
        }
    },
    smile: {
        label: 'Smile',
        color: '#FFD93D',
        draw(ctx, size) {
            const cx = size / 2;
            const cy = size / 2;
            const r = size * 0.32;
            ctx.fillStyle = this.color;
            ctx.beginPath();
            ctx.arc(cx, cy, r, 0, Math.PI * 2);
            ctx.fill();

            ctx.fillStyle = '#333';
            ctx.beginPath();
            ctx.arc(cx - r * 0.35, cy - r * 0.2, r * 0.1, 0, Math.PI * 2);
            ctx.fill();
            ctx.beginPath();
            ctx.arc(cx + r * 0.35, cy - r * 0.2, r * 0.1, 0, Math.PI * 2);
            ctx.fill();

            ctx.strokeStyle = '#333';
            ctx.lineWidth = size * 0.025;
            ctx.beginPath();
            ctx.arc(cx, cy + r * 0.05, r * 0.45, 0.15 * Math.PI, 0.85 * Math.PI);
            ctx.stroke();
        }
    },
    ...createNumberPatterns(),
    ...createLetterPatterns(),
    circle: createCirclePattern('#A8E6CF', 'Circle'),
    triangle: createTrianglePattern('#F7DC6F', 'Triangle'),
    square: createSquarePattern('#F8C471', 'Square'),
    diamond: createDiamondPattern('#BB8FCE', 'Diamond'),
    plus: createPlusPattern('#F1948A', 'Plus')
};

function resolvePatternFace(patternIdOrFace, rotation, transformOptions) {
    if (patternIdOrFace && typeof patternIdOrFace === 'object' && typeof patternIdOrFace.patternId === 'string') {
        return {
            patternId: patternIdOrFace.patternId,
            rotation: Number.isFinite(Number(patternIdOrFace.rotation)) ? Number(patternIdOrFace.rotation) : 0
        };
    }

    return {
        patternId: patternIdOrFace,
        rotation: Number.isFinite(Number(rotation)) ? Number(rotation) : 0
    };
}

/**
 * Draw a pattern onto a canvas context with rotation.
 * @param {CanvasRenderingContext2D} ctx
 * @param {string|object} patternIdOrFace
 * @param {number} rotation
 * @param {number} x
 * @param {number} y
 * @param {number} size
 * @param {string} [bgColor]
 * @param {object} [transformOptions]
 */
function drawPattern(ctx, patternIdOrFace, rotation, x, y, size, bgColor, transformOptions) {
    const face = resolvePatternFace(patternIdOrFace, rotation, transformOptions);
    const pattern = PATTERNS[face.patternId];

    ctx.save();
    ctx.beginPath();
    ctx.rect(x, y, size, size);
    ctx.clip();

    if (bgColor) {
        ctx.fillStyle = bgColor;
        ctx.fillRect(x, y, size, size);
    }

    ctx.translate(x + size / 2, y + size / 2);
    ctx.rotate((face.rotation * Math.PI) / 180);
    ctx.translate(-size / 2, -size / 2);

    if (pattern) {
        pattern.draw(ctx, size);
    } else {
        ctx.fillStyle = '#fff';
        ctx.font = `bold ${size * 0.4}px ${BASE_TEXT_FONT}`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(face.patternId, size / 2, size / 2);
    }

    ctx.restore();
}

/**
 * Generate a face texture as an offscreen canvas.
 * Accepts either `(patternId, rotation, size, bgColor, transformOptions)`
 * or `(faceObject, size, bgColor)`.
 */
function generateFaceTexture(patternIdOrFace, rotationOrSize, sizeOrBgColor, bgColor, transformOptions) {
    let patternId = patternIdOrFace;
    let rotation = rotationOrSize;
    let size = sizeOrBgColor;
    let background = bgColor;
    let transform = transformOptions;

    if (patternIdOrFace && typeof patternIdOrFace === 'object' && typeof patternIdOrFace.patternId === 'string') {
        patternId = patternIdOrFace.patternId;
        rotation = patternIdOrFace.rotation;
        size = rotationOrSize;
        background = sizeOrBgColor;
        transform = patternIdOrFace;
    }

    const canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext('2d');
    drawPattern(ctx, patternId, rotation, 0, 0, size, background, transform);
    return canvas;
}

function getAllPatternIds() {
    return Object.keys(PATTERNS);
}

function getPatternLabel(patternId) {
    return PATTERNS[patternId]?.label || patternId;
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        PATTERNS,
        drawPattern,
        generateFaceTexture,
        getAllPatternIds,
        getPatternLabel
    };
}
