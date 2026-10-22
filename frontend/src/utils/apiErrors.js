import axios from 'axios'

function detailText(value) {
  if (typeof value === 'string') return value.trim()
  if (Array.isArray(value)) return value.map(detailText).filter(Boolean).join('；')
  if (value && typeof value === 'object') {
    return detailText(value.detail || value.msg || value.message || value.error)
  }
  return ''
}

export async function getErrorMessage(error, fallback = '请求失败，请稍后重试') {
  let data = error?.response?.data
  if (typeof Blob !== 'undefined' && data instanceof Blob) {
    try { data = JSON.parse(await data.text()) } catch { data = null }
  }
  if (typeof data === 'string') {
    try { data = JSON.parse(data) } catch { data = null }
  }
  const detail = detailText(data)
  if (detail) return detail
  if (error?.code === 'ECONNABORTED' || error?.code === 'ETIMEDOUT')
    return '请求超时，请稍后重试'
  if (error?.code === 'ERR_NETWORK' || (error instanceof TypeError && error.message === 'Failed to fetch'))
    return '无法连接服务器，请检查网络连接后重试'
  const status = error?.response?.status
  if (status === 401) return /(?:^|\/)auth\/login(?:\?|$)/.test(error?.config?.url || '')
    ? '用户名或密码错误'
    : '登录状态已失效，请重新登录'
  if (status === 403) return '没有权限执行此操作'
  if (status === 404) return '请求的资源不存在或已被删除'
  if (status === 413) return '上传文件过大，请减小文件后重试'
  if (status === 422) return '输入格式不正确，请检查后重试'
  if (status === 429) return '请求过于频繁，请稍后重试'
  if (status >= 500) return '服务器处理失败，请稍后重试'
  return status ? fallback : (error?.message || fallback)
}

// Share reporting between Axios, streaming fetch and local handlers. One failure gets one toast.
export function createErrorReporter({ notify, getToken, expireSession }) {
  const reported = new WeakSet()
  return async function reportError(error, fallback) {
    if (axios.isCancel(error) || error?.name === 'AbortError' || error === 'cancel' || error === 'close') return
    const trackable = error && typeof error === 'object'
    if (trackable && reported.has(error)) return
    if (trackable) reported.add(error)
    const config = error?.config || {}
    const authForm = /(?:^|\/)auth\/(?:login|register)(?:\?|$)/.test(config.url || '')
    if (error?.response?.status === 401 && !authForm) {
      const authorization = config.headers?.Authorization || config.headers?.get?.('Authorization')
      // A delayed failure from the previous account must not log out a newer session.
      if (authorization && authorization !== `Bearer ${getToken()}`) return
      notify('登录状态已失效，请重新登录')
      expireSession()
      return
    }
    notify(await getErrorMessage(error, fallback))
  }
}
