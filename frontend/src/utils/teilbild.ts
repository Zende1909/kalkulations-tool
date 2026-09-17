const MAX_EDGE_PX = 800;
const JPEG_QUALITY = 0.85;
const MAX_FILE_BYTES = 4 * 1024 * 1024;

export type TeilbildErrorCode =
  | "spritzguss.fileReadFailed"
  | "spritzguss.imageLoadFailed"
  | "spritzguss.canvasUnavailable"
  | "spritzguss.imageCompressFailed"
  | "spritzguss.imageFileRequired"
  | "spritzguss.imageTooLarge";

export class TeilbildError extends Error {
  readonly code: TeilbildErrorCode;

  constructor(code: TeilbildErrorCode) {
    super(code);
    this.name = "TeilbildError";
    this.code = code;
  }
}

export function teilbildSrc(
  mime: string | null | undefined,
  data: string | null | undefined,
): string | null {
  if (!mime || !data) return null;
  return `data:${mime};base64,${data}`;
}

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(new TeilbildError("spritzguss.fileReadFailed"));
    reader.readAsDataURL(file);
  });
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new TeilbildError("spritzguss.imageLoadFailed"));
    img.src = src;
  });
}

async function compressDataUrl(dataUrl: string): Promise<{ mime: string; data: string }> {
  const img = await loadImage(dataUrl);
  const scale = Math.min(1, MAX_EDGE_PX / Math.max(img.width, img.height));
  const width = Math.max(1, Math.round(img.width * scale));
  const height = Math.max(1, Math.round(img.height * scale));
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new TeilbildError("spritzguss.canvasUnavailable");
  ctx.drawImage(img, 0, 0, width, height);
  const compressed = canvas.toDataURL("image/jpeg", JPEG_QUALITY);
  const match = /^data:(image\/[a-zA-Z0-9.+-]+);base64,(.+)$/.exec(compressed);
  if (!match) throw new TeilbildError("spritzguss.imageCompressFailed");
  return { mime: match[1], data: match[2] };
}

export async function processTeilbildFile(file: File): Promise<{ mime: string; data: string }> {
  if (!file.type.startsWith("image/")) {
    throw new TeilbildError("spritzguss.imageFileRequired");
  }
  if (file.size > MAX_FILE_BYTES) {
    throw new TeilbildError("spritzguss.imageTooLarge");
  }
  const dataUrl = await readFileAsDataUrl(file);
  return compressDataUrl(dataUrl);
}
