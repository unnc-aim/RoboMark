import axios from 'axios'
import { message } from '../shared/ui/feedback'
import { createErrorReporter } from './apiErrors'

const STORAGE_KEY = 'robomark-token'

export const reportError = createErrorReporter({
  notify: text => message.error(text, { id: `request-error:${text}` }),
  getToken: () => localStorage.getItem(STORAGE_KEY),
  expireSession: () => {
    localStorage.removeItem(STORAGE_KEY)
    localStorage.removeItem('robomark-user')
    window.dispatchEvent(new CustomEvent('robomark:session-expired'))
  }
})

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' }
})

api.interceptors.request.use(config => {
  const token = localStorage.getItem(STORAGE_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(response => response, async error => {
  await reportError(error)
  return Promise.reject(error)
})

// Streaming responses cannot use Axios' browser adapter, but need the same auth and errors.
export async function apiFetch(url, options = {}) {
  const headers = new Headers(options.headers)
  const token = localStorage.getItem(STORAGE_KEY)
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const config = { url, headers }
  try {
    const response = await fetch(url, { ...options, headers })
    if (!response.ok) {
      let data
      try { data = await response.json() } catch { /* status fallback handles non-JSON errors */ }
      throw Object.assign(new Error('请求失败'), { config, response: { status: response.status, data } })
    }
    return response
  } catch (error) {
    // Fetch network errors lack Axios' request metadata.
    if (error && typeof error === 'object') error.config = config
    await reportError(error)
    throw error
  }
}

export default api
