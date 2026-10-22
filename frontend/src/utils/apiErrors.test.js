import assert from 'node:assert/strict'
import test from 'node:test'
import axios from 'axios'
import { createErrorReporter, getErrorMessage } from './apiErrors.js'

function fixture() {
  let token = 'old'
  const notifications = []
  let expired = 0
  const report = createErrorReporter({
    notify: text => notifications.push(text),
    getToken: () => token,
    expireSession: () => { token = null; expired++ }
  })
  return { report, notifications, setToken: value => { token = value }, get expired() { return expired } }
}
const failure = (status, data, url = '/datasets', token = 'old') => ({
  config: { url, headers: { Authorization: `Bearer ${token}` } }, response: { status, data }
})

test('invalid credentials notify without clearing the session; local reporting does not duplicate', async () => {
  const f = fixture()
  const error = failure(401, { detail: '用户名或密码错误' }, '/auth/login')
  await f.report(error)
  await f.report(error, '登录失败')
  assert.deepEqual(f.notifications, ['用户名或密码错误'])
  assert.equal(f.expired, 0)
  assert.equal(await getErrorMessage(failure(401, null, '/auth/login')), '用户名或密码错误')
})

test('concurrent authenticated 401 failures expire once; stale failures cannot log out a newer account', async () => {
  const f = fixture()
  await Promise.all([f.report(failure(401)), f.report(failure(401))])
  assert.equal(f.expired, 1)
  assert.deepEqual(f.notifications, ['登录状态已失效，请重新登录'])
  f.setToken('new')
  await f.report(failure(401))
  assert.equal(f.expired, 1)
})

test('fetch Headers also enforce session freshness', async () => {
  const f = fixture()
  const error = failure(401)
  error.config.headers = new Headers({ Authorization: 'Bearer old' })
  await f.report(error)
  assert.equal(f.expired, 1)
})

test('cancelled requests and dismissed confirmations do not notify', async () => {
  const f = fixture()
  for (const error of [new axios.CanceledError(), new DOMException('aborted', 'AbortError'), 'cancel', 'close']) await f.report(error)
  assert.deepEqual(f.notifications, [])
})

test('all HTTP failures report, including background requests and string or object details', async () => {
  const f = fixture()
  for (const status of [400, 403, 404, 409, 413, 422, 429, 500, 502, 503]) {
    const error = failure(status, { detail: `请求失败 ${status}` })
    error.config.silentError = true
    await f.report(error)
  }
  assert.equal(f.notifications.length, 10)
  assert.equal(await getErrorMessage(failure(422, { detail: [{ msg: '字段必填' }, { msg: '格式错误' }] })), '字段必填；格式错误')
  assert.equal(await getErrorMessage(failure(409, { detail: { message: '标注已被其他用户修改' } })), '标注已被其他用户修改')
})

test('download Blob errors preserve server details; HTML and unknown status errors have readable fallbacks', async () => {
  const error = failure(404, new Blob([JSON.stringify({ detail: '导出文件已过期' })]))
  assert.equal(await getErrorMessage(error), '导出文件已过期')
  assert.equal(await getErrorMessage(failure(502, '<html>Bad Gateway</html>')), '服务器处理失败，请稍后重试')
  assert.equal(await getErrorMessage(failure(418, null)), '请求失败，请稍后重试')
  assert.equal(await getErrorMessage(failure(413, null)), '上传文件过大，请减小文件后重试')
})

test('network failures and timeouts notify without invalidating credentials', async () => {
  const f = fixture()
  await f.report({ code: 'ERR_NETWORK' })
  await f.report({ code: 'ECONNABORTED' })
  await f.report(new TypeError('Failed to fetch'))
  assert.deepEqual(f.notifications, ['无法连接服务器，请检查网络连接后重试', '请求超时，请稍后重试', '无法连接服务器，请检查网络连接后重试'])
  assert.equal(f.expired, 0)
})
