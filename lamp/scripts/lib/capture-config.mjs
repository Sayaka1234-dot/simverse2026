import path from 'node:path';

export function buildCaptureUrl({ baseUrl, levelFile }) {
  return `${baseUrl}/capture.html?level=${encodeURIComponent(levelFile)}&export=png`;
}

export function buildImageOutputPath({ imagesDir, levelId }) {
  return path.join(imagesDir, `${levelId}.png`);
}

export function extractCanvasImageDataUrl(dumpedDom) {
  const match = dumpedDom.match(
    /<textarea[^>]*id="capture-output"[^>]*>\s*(data:image\/png;base64,[A-Za-z0-9+/=\s]+?)\s*<\/textarea>/i
  );

  if (!match) {
    throw new Error('Capture page did not export a canvas PNG payload.');
  }

  return match[1].replace(/\s+/g, '');
}

export function decodeCanvasImageDataUrl(dataUrl) {
  const prefix = 'data:image/png;base64,';

  if (!dataUrl.startsWith(prefix)) {
    throw new Error('Capture export is not a PNG data URL.');
  }

  return Buffer.from(dataUrl.slice(prefix.length), 'base64');
}
