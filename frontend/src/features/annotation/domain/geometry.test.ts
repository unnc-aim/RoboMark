import test from "node:test";
import assert from "node:assert/strict";
import { lineIntersection, pointInPolygon } from "./geometry.ts";
test("eight point edges produce normalized intersection; parallel edges reject", () => {
  assert.deepEqual(
    lineIntersection(
      { x: 0, y: 50 },
      { x: 100, y: 50 },
      { x: 50, y: 0 },
      { x: 50, y: 100 },
      100,
      100,
    ),
    { x: 0.5, y: 0.5 },
  );
  assert.equal(
    lineIntersection(
      { x: 0, y: 0 },
      { x: 100, y: 0 },
      { x: 0, y: 50 },
      { x: 100, y: 50 },
      100,
      100,
    ),
    null,
  );
});
test("polygon hit testing distinguishes rotated quadrilateral interior from its bounding box", () => {
  const polygon = [
    { x: 0, y: 1 },
    { x: 1, y: 0 },
    { x: 2, y: 1 },
    { x: 1, y: 2 },
  ];
  assert.equal(pointInPolygon({ x: 1, y: 1 }, polygon), true);
  assert.equal(pointInPolygon({ x: 0.1, y: 0.1 }, polygon), false);
});
