export function parseCategoryKeys(value?: string | null): string[] {
  return [
    ...new Set(
      (value || "")
        .split(",")
        .map((key) => key.trim().toLowerCase())
        .filter(Boolean),
    ),
  ];
}
export function eventShortcut(
  event: Pick<
    KeyboardEvent,
    "key" | "ctrlKey" | "metaKey" | "shiftKey" | "altKey"
  >,
): string | null {
  if (
    ["Control", "Meta", "Shift", "Alt", "Tab", "Escape", "Enter"].includes(
      event.key,
    )
  )
    return null;
  return [
    event.ctrlKey || event.metaKey ? "ctrl" : "",
    event.altKey ? "alt" : "",
    event.shiftKey ? "shift" : "",
    event.key.toLowerCase(),
  ]
    .filter(Boolean)
    .join("+");
}
export function categoryShortcutConflict(
  categories: { id: number; name: string; shortcut_key?: string | null }[],
  id: number | null,
  keys: string[],
) {
  return categories.find(
    (category) =>
      category.id !== id &&
      parseCategoryKeys(category.shortcut_key).some((key) =>
        keys.includes(key),
      ),
  );
}
// Global editor commands must keep precedence over category selection.
export const reservedCategoryKeys = [
  "v",
  "h",
  "n",
  "?",
  "delete",
  "backspace",
  "arrowleft",
  "arrowright",
  "escape",
  "enter",
  "tab",
  "ctrl+s",
  "ctrl+z",
  "ctrl+shift+z",
  "ctrl+enter",
];
