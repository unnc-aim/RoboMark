import fs from "node:fs";
import path from "node:path";
import { parse } from "vue/compiler-sfc";
const root = new URL("../src/", import.meta.url).pathname;
const failures = [];
function scan(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      if (file !== path.join(root, "shared", "ui")) scan(file);
      continue;
    }
    if (!/\.(vue|js|ts)$/.test(file)) continue;
    const source = fs.readFileSync(file, "utf8");
    if (/(?:element-plus|<\/?el-)/.test(source))
      failures.push(`${file}: legacy component library`);
    if (!file.endsWith(".vue")) continue;
    const { descriptor, errors } = parse(source, { filename: file });
    if (errors.length) failures.push(`${file}: invalid Vue source`);
    function visit(node) {
      if (node.type === 1) {
        if (
          [
            "details",
            "summary",
            "button",
            "input",
            "select",
            "textarea",
            "option",
            "dialog",
            "table",
            "form",
            "progress",
            "a",
            "kbd",
          ].includes(node.tag)
        )
          failures.push(
            `${file}:${node.loc.start.line}: native control <${node.tag}>`,
          );
        if (
          /^[a-z]/.test(node.tag) &&
          !node.tag.startsWith("ui-") &&
          node.tag !== "canvas" &&
          node.props.some(
            (p) =>
              p.type === 7 &&
              p.name === "on" &&
              ["click", "keydown"].includes(p.arg?.content),
          )
        )
          failures.push(
            `${file}:${node.loc.start.line}: native interactive <${node.tag}>`,
          );
      }
      for (const child of node.children || []) visit(child);
    }
    if (descriptor.template?.ast) visit(descriptor.template.ast);
  }
}
scan(root);
if (failures.length) {
  console.error(failures.join("\n"));
  process.exitCode = 1;
} else
  console.log(
    "UI boundary passed: no native controls or Element Plus outside the shared component library.",
  );
