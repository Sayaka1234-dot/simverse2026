import CTRGameObject from "@/game/CTRGameObject";
import ResourceId from "@/resources/ResourceId";
import Vector from "@/core/Vector";
import Radians from "@/utils/Radians";
import Canvas from "@/utils/Canvas";

const SPIKES_HEIGHT = 10;

class Spikes extends CTRGameObject {
    t1: Vector;
    t2: Vector;
    b1: Vector;
    b2: Vector;
    angle: number;

    constructor(px: number, py: number, width: number, angle: number) {
        super();

        // select and load the spikes image
        let imageId: number | undefined;
        switch (width) {
            case 1:
                imageId = ResourceId.IMG_OBJ_SPIKES_01;
                break;
            case 2:
                imageId = ResourceId.IMG_OBJ_SPIKES_02;
                break;
            case 3:
                imageId = ResourceId.IMG_OBJ_SPIKES_03;
                break;
            case 4:
                imageId = ResourceId.IMG_OBJ_SPIKES_04;
                break;
            default:
                imageId = ResourceId.IMG_OBJ_SPIKES_01;
                break;
        }
        this.initTextureWithId(imageId);

        this.passColorToChilds = false;
        this.rotation = angle;

        this.t1 = Vector.newZero();
        this.t2 = Vector.newZero();
        this.b1 = Vector.newZero();
        this.b2 = Vector.newZero();

        this.x = px;
        this.y = py;

        this.angle = 0;

        this.updateRotation();
    }

    updateRotation() {
        const texture = this.texture;
        if (!texture) {
            return;
        }

        const quadIndex = this.quadToDraw;
        const rect = quadIndex !== undefined ? texture.rects[quadIndex] : null;
        const pWidth = (rect?.w ?? this.width) / 2;

        this.t1.x = this.x - pWidth;
        this.t2.x = this.x + pWidth;
        this.t1.y = this.t2.y = this.y - SPIKES_HEIGHT / 2.0;

        this.b1.x = this.t1.x;
        this.b2.x = this.t2.x;
        this.b1.y = this.b2.y = this.y + SPIKES_HEIGHT / 2.0;

        this.angle = Radians.fromDegrees(this.rotation);

        this.t1.rotateAround(this.angle, this.x, this.y);
        this.t2.rotateAround(this.angle, this.x, this.y);
        this.b1.rotateAround(this.angle, this.x, this.y);
        this.b2.rotateAround(this.angle, this.x, this.y);
    }

    override update(delta: number) {
        super.update(delta);

        if (this.mover) {
            this.updateRotation();
        }
    }

    override drawBB() {
        const ctx = Canvas.context;
        if (ctx) {
            ctx.beginPath();
            ctx.strokeStyle = "red";
            ctx.moveTo(this.t1.x, this.t1.y);
            ctx.lineTo(this.t2.x, this.t2.y);
            ctx.lineTo(this.b2.x, this.b2.y);
            ctx.lineTo(this.b1.x, this.b1.y);
            ctx.lineTo(this.t1.x, this.t1.y);
            ctx.closePath();
            ctx.stroke();
        }
    }
}

export default Spikes;
