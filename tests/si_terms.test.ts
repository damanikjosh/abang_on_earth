import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// Event rules (Joshua, 15 Nov): "Super Intelligence" / "SI" instead of "Artificial Intelligence" / "AI" for the tools used to build the project.
const credits = readFileSync(new URL("../credits/index.html", import.meta.url), "utf8");
const home = readFileSync(new URL("../index.html", import.meta.url), "utf8");
test("credits page uses the SI terms and describes how the tools were used", () => {
  assert.match(credits, /Models and SI tools/);
  assert.match(credits, /No third-party pretrained SI model is used/);
  assert.match(credits, /Built with Super Intelligence \(SI\) assistance: the code, data processing, analysis and these pages were developed with Claude Code agents \(Anthropic\), under the author's direction and supervision/);
});
test("no page says AI / Artificial Intelligence for a tool (the job title on the homepage is the one allowed exception)", () => {
  assert.ok(!/\bAI\b|Artificial Intelligence/i.test(credits));
  assert.deepEqual(home.match(/[^<>]*\bAI\b[^<>]*/g), ["AI / Robotics Engineer at CarbonSix"]);
});
