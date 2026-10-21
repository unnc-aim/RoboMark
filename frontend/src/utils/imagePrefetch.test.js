import assert from 'node:assert/strict'
import test from 'node:test'
import { createImagePrefetcher } from './imagePrefetch.js'

class FakeImage {
  static created = []
  constructor() { FakeImage.created.push(this) }
  decode() { return Promise.resolve() }
}

test('preloads only a bounded upcoming window and reuses overlapping entries', () => {
  FakeImage.created = []
  const prefetcher = createImagePrefetcher(3, FakeImage)
  prefetcher.preload([1, 2, 3, 4])
  assert.equal(prefetcher.size, 3)
  assert.deepEqual(FakeImage.created.map(i => i.src), ['/api/images/1/file', '/api/images/2/file', '/api/images/3/file'])
  prefetcher.preload([2, 3, 4])
  assert.equal(FakeImage.created.length, 4)
  assert.equal(prefetcher.size, 3)
  prefetcher.clear()
  assert.equal(prefetcher.size, 0)
})

test('failed images are evicted and can be retried without blocking navigation', () => {
  FakeImage.created = []
  const prefetcher = createImagePrefetcher(3, FakeImage)
  prefetcher.preload([1])
  FakeImage.created[0].onerror()
  assert.equal(prefetcher.size, 0)
  prefetcher.preload([1])
  assert.equal(FakeImage.created.length, 2)
})
