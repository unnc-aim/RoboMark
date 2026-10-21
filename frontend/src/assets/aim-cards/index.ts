import manifest from "./manifest.json";

const images = import.meta.glob<string>("./*.webp", {
  eager: true,
  query: "?url",
  import: "default",
});

export const cards = manifest.map(({ file, name }) => {
  const src = images[`./${file}`];
  if (!src) throw new Error(`Missing AIM card asset: ${file}`);
  return { src, alt: `${name} · AIM 五周年纪念卡牌` };
});
