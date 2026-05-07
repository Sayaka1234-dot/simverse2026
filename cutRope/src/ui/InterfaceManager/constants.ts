import edition from "@/config/editions/net-edition";
import ResourceId from "@/resources/ResourceId";
import SnowfallOverlay from "@/ui/SnowfallOverlay";
import { IS_XMAS } from "@/utils/SpecialEvents";

const customMenuMusic = edition.menuMusicId;
const resolvedMenuMusicId =
    typeof customMenuMusic === "number"
        ? customMenuMusic
        : typeof customMenuMusic === "string"
          ? ResourceId[customMenuMusic as keyof typeof ResourceId]
          : undefined;

export const MENU_MUSIC_ID =
    resolvedMenuMusicId ?? (IS_XMAS ? ResourceId.SND_MENU_MUSIC_XMAS : ResourceId.SND_MENU_MUSIC);

export const IS_MSIE_BROWSER = /MSIE|Trident/.test(window.navigator.userAgent);

export const startSnow = () => {
    if (IS_XMAS) {
        SnowfallOverlay.start();
    }
};

export const stopSnow = () => {
    if (IS_XMAS) {
        SnowfallOverlay.stop();
    }
};

// Helper function to get the default box index based on holiday period
// Simplified flow: single unified level list
export const getDefaultBoxIndex = () => {
    return 0;
};
