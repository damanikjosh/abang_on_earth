// the drivers classes are told apart under colour-vision deficiency and do not collide with the fire layers' colours.
// Machado et al. 2009 matrices (severity 1.0), CIE76 delta E in Lab. Thresholds: classes among themselves >= 10; classes vs every fire colour >= 8.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const MAT: Record<string, number[][]> = {
  normal: [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
  protan: [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]],
  deutan: [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.01182, 0.04294, 0.968881]],
  tritan: [[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602], [0.004733, 0.691367, 0.3039]],
};
const rgb = (h: string) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16) / 255);
const lin = (c: number) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
const gam = (c: number) => { c = Math.min(1, Math.max(0, c)); return c <= 0.0031308 ? 12.92 * c : 1.055 * c ** (1 / 2.4) - 0.055; };
const mul = (m: number[][], v: number[]) => m.map((r) => r[0] * v[0] + r[1] * v[1] + r[2] * v[2]);
function lab(c: number[]): number[] {
  const [r, g, b] = c.map(lin), X = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047, Y = 0.2126 * r + 0.7152 * g + 0.0722 * b, Z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883;
  const f = (t: number) => (t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116);
  return [116 * f(Y) - 16, 500 * (f(X) - f(Y)), 200 * (f(Y) - f(Z))];
}
const seen = (hex: string, k: string) => lab(mul(MAT[k], rgb(hex).map(lin)).map(gam));
const dE = (a: string, b: string, k: string) => Math.hypot(...seen(a, k).map((v, i) => v - seen(b, k)[i]));

const L = JSON.parse(readFileSync("public/data-v4/layers.json", "utf8")).layers as { id: string; classes?: { label: string; color: string }[] }[];
const classes = L.find((l) => l.id === "drivers")!.classes!.map((c) => c.color);
// the two default-on fire layers (MODIS orange, VIIRS pink-red). The "forest-loss fires" layers (green, blue; off by default) share hues with some classes by design of those layers: documented in the PR, not tested.
const fire = (JSON.parse(readFileSync("public/data-v4/manifest.json", "utf8")).fire_layers.layers as { id: string; color: string[] }[]).filter((d) => d.id === "modis" || d.id === "viirs").flatMap((d) => (Array.isArray(d.color) ? d.color : [d.color])).filter((c) => /^#/.test(c));

test("drivers classes: min delta E among themselves >= 10 for normal, protan, deutan and tritan vision", () => {
  for (const k of Object.keys(MAT)) for (let i = 0; i < classes.length; i++) for (let j = i + 1; j < classes.length; j++) assert.ok(dE(classes[i], classes[j], k) >= 10, `${k}: ${classes[i]} vs ${classes[j]} = ${dE(classes[i], classes[j], k).toFixed(1)}`);
});
test("drivers classes vs the fire layers' colours: delta E >= 8 for every vision type", () => {
  assert.equal(fire.length, 8);
  for (const k of Object.keys(MAT)) for (const c of classes) for (const f of fire) assert.ok(dE(c, f, k) >= 8, `${k}: class ${c} vs fire ${f} = ${dE(c, f, k).toFixed(1)}`);
});
