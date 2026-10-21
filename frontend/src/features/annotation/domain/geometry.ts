export interface Point {
  x: number;
  y: number;
}
/** Normalized intersection of the infinite lines used by eight-point annotation. */
export function lineIntersection(
  p1: Point,
  p2: Point,
  p3: Point,
  p4: Point,
  width: number,
  height: number,
): Point | null {
  const denominator =
    (p1.x - p2.x) * (p3.y - p4.y) - (p1.y - p2.y) * (p3.x - p4.x);
  if (Math.abs(denominator) < 1e-10 || width <= 0 || height <= 0) return null;
  const t =
    ((p1.x - p3.x) * (p3.y - p4.y) - (p1.y - p3.y) * (p3.x - p4.x)) /
    denominator;
  return {
    x: (p1.x + t * (p2.x - p1.x)) / width,
    y: (p1.y + t * (p2.y - p1.y)) / height,
  };
}
export function pointInPolygon(point: Point, polygon: Point[]): boolean {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const a = polygon[i],
      b = polygon[j];
    if (
      a.y > point.y !== b.y > point.y &&
      point.x < ((b.x - a.x) * (point.y - a.y)) / (b.y - a.y) + a.x
    )
      inside = !inside;
  }
  return inside;
}
