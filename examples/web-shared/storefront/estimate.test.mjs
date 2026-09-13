import assert from "node:assert/strict";
import test from "node:test";
import { splitEstimate } from "./estimate.mjs";

const cases = [
  ["plain ISO date", "2026-08-23", null],
  ["ordinary note", "2026-08-23 (revised)", { date: "2026-08-23", note: "revised" }],
  ["trailing whitespace", "2026-08-23 (revised)  ", { date: "2026-08-23", note: "revised" }],
  ["adjacent multiple parentheses", "2026-08-23(foo)(bar)", { date: "2026-08-23(foo)", note: "bar" }],
  ["separated multiple parentheses", "2026-08-23 (foo)(bar)", { date: "2026-08-23", note: "foo)(bar" }],
  ["incomplete note", "2026-08-23 (revised", null],
  ["line feed in note", "2026-08-23(note\nx)", null],
  ["carriage return in note", "2026-08-23(note\rx)", null],
  ["line separator in note", "2026-08-23(note\u2028x)", null],
  ["paragraph separator in note", "2026-08-23(note\u2029x)", null],
];

for (const [name, input, expected] of cases) {
  test(name, () => assert.deepEqual(splitEstimate(input), expected));
}

test("long hostile input is handled without backtracking", () => {
  const input = `!(${"!(!".repeat(200_000)}`;
  assert.equal(splitEstimate(input), null);
});
