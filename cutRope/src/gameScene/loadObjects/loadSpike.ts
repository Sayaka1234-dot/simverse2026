import Spikes from "@/game/Spikes";
import type GameSceneLoaders from "../loaders";
import type { SpikeItem } from "../MapLayerItem";

export function loadSpike(this: GameSceneLoaders, item: SpikeItem): void {
    if (typeof item.toggled === "number" && item.toggled > 0) {
        return;
    }

    const px = item.x * this.PM + this.PMX;
    const py = item.y * this.PM + this.PMY;
    const w = item.size;
    const a = item.angle ?? 0;
    const s = new Spikes(px, py, w, a);
    s.parseMover(item as Parameters<typeof s.parseMover>[0]);
    this.spikes.push(s);
}
