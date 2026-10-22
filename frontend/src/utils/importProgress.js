// SSE frames and UTF-8 characters may span arbitrary network chunks.
export async function readImportProgress(body, onProgress) {
  if (!body) throw new Error('无法读取导入进度，请刷新数据集列表确认结果')
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let completed = false
  function frame(text) {
    const payload = text.split(/\r?\n/).filter(line => line.startsWith('data:'))
      .map(line => line.slice(5).trimStart()).join('\n')
    if (!payload) return
    let data
    try { data = JSON.parse(payload) } catch { throw new Error('导入进度解析失败，请刷新数据集列表确认结果') }
    if (data.status === 'error') throw new Error(data.message || '批量导入失败')
    onProgress(data)
    if (data.status === 'done') completed = true
  }
  try {
    while (!completed) {
      const { done, value } = await reader.read()
      buffer += decoder.decode(value, { stream: !done })
      let boundary
      while ((boundary = /\r?\n\r?\n/.exec(buffer))) {
        frame(buffer.slice(0, boundary.index))
        buffer = buffer.slice(boundary.index + boundary[0].length)
        if (completed) break
      }
      if (done) {
        if (!completed && buffer.trim()) frame(buffer)
        break
      }
    }
    if (!completed) throw new Error('导入连接中断，请刷新数据集列表确认已导入内容后重试')
  } finally {
    try { await reader.cancel() } finally { reader.releaseLock() }
  }
}
