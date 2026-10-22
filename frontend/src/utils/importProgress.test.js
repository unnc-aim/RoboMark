import assert from 'node:assert/strict'
import test from 'node:test'
import { readImportProgress } from './importProgress.js'

function stream(chunks) {
  return new ReadableStream({ start(controller) {
    chunks.forEach(chunk => controller.enqueue(chunk))
    controller.close()
  } })
}
const encode = text => new TextEncoder().encode(text)

test('split UTF-8 characters and SSE boundaries still deliver the terminal result', async () => {
  const bytes = encode('data: {"status":"importing","message":"正在导入"}\r\n\r\ndata: {"status":"done","message":"完成"}\r\n\r\n')
  const rows = []
  await readImportProgress(stream(Array.from(bytes, byte => new Uint8Array([byte]))), row => rows.push(row))
  assert.deepEqual(rows.map(row => row.message), ['正在导入', '完成'])
})

test('server failures, malformed events and premature EOF cannot look successful', async () => {
  for (const [input, expected] of [
    ['data: {"status":"error","message":"目录不可读"}\n\n', /目录不可读/],
    ['data: not-json\n\n', /解析失败/],
    ['data: {"status":"importing"}\n\n', /连接中断/],
    ['', /连接中断/]
  ]) await assert.rejects(readImportProgress(stream([encode(input)]), () => {}), expected)
  await assert.rejects(readImportProgress(null, () => {}), /无法读取/)
})

test('the last terminal event is accepted even without a trailing frame delimiter', async () => {
  const rows = []
  await readImportProgress(stream([encode('data: {"status":"done"}')]), row => rows.push(row))
  assert.equal(rows[0].status, 'done')
})
