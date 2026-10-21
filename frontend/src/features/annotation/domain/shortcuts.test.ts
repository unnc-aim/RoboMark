import test from "node:test";
import assert from "node:assert/strict";
import {
  parseCategoryKeys,
  eventShortcut,
  categoryShortcutConflict,
} from "./shortcuts.ts";
test("category shortcut aliases and modifiers normalize without losing Mac command support", () => {
  assert.deepEqual(parseCategoryKeys("1,B, b,,ctrl+q"), ["1", "b", "ctrl+q"]);
  assert.equal(
    eventShortcut({
      key: "Q",
      ctrlKey: false,
      metaKey: true,
      altKey: false,
      shiftKey: true,
    }),
    "ctrl+shift+q",
  );
  assert.equal(
    eventShortcut({
      key: "Shift",
      ctrlKey: false,
      metaKey: false,
      altKey: false,
      shiftKey: true,
    }),
    null,
  );
});
test("overlapping aliases conflict, editing own aliases does not", () => {
  const categories = [
    { id: 1, name: "blue", shortcut_key: "1,b" },
    { id: 2, name: "red", shortcut_key: "2,r" },
  ];
  assert.equal(categoryShortcutConflict(categories, 2, ["b"])?.id, 1);
  assert.equal(categoryShortcutConflict(categories, 1, ["b"]), undefined);
});
