/**
 * Sequential single-hue (blue) scale for map magnitude encoding.
 * Endpoints match the validated palette's blue ramp (step 100 -> step 700).
 * Pure UI color interpolation — does not alter or derive any data value.
 */
const LIGHT_HEX = "#cde2fb";
const DARK_HEX = "#0d366b";

function hexToRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function rgbToHex([r, g, b]: [number, number, number]): string {
  return `#${[r, g, b].map((c) => Math.round(c).toString(16).padStart(2, "0")).join("")}`;
}

export function sequentialBlue(t: number): string {
  const clamped = Math.max(0, Math.min(1, t));
  const a = hexToRgb(LIGHT_HEX);
  const b = hexToRgb(DARK_HEX);
  const mixed: [number, number, number] = [
    a[0] + (b[0] - a[0]) * clamped,
    a[1] + (b[1] - a[1]) * clamped,
    a[2] + (b[2] - a[2]) * clamped,
  ];
  return rgbToHex(mixed);
}

export const SEQUENTIAL_BLUE_LIGHT = LIGHT_HEX;
export const SEQUENTIAL_BLUE_DARK = DARK_HEX;

export function normalize(value: number, min: number, max: number): number {
  if (max === min) return 0.5;
  return (value - min) / (max - min);
}
