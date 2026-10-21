// Keep a small decoded image window. The canvas uses the same public image URLs.
export function createImagePrefetcher(limit = 6, ImageClass = Image) {
  const cache = new Map()
  function preload(ids) {
    const wanted = new Set(ids.slice(0, limit))
    for (const id of cache.keys()) if (!wanted.has(id)) cache.delete(id)
    for (const id of wanted) {
      if (cache.has(id)) continue
      const image = new ImageClass()
      cache.set(id, image)
      image.onerror = () => { if (cache.get(id) === image) cache.delete(id) }
      image.src = `/api/images/${id}/file`
      image.decode?.().catch(() => {})
    }
  }
  return { preload, clear: () => cache.clear(), get size() { return cache.size } }
}
