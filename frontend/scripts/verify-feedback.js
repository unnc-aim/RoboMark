// Run from the repository root with playwright-cli run-code --filename.
// Exercises failure notifications through real controls; all business APIs are mocked.
async (page) => {
  page.setDefaultTimeout(8000);
  const results = [], errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const user = { id: 1, username: '通知验收', is_admin: true, is_active: true };
  const dataset = { id: 1, name: '验收数据集', image_path: '/test/images', label_path: '/test/labels', total_images: 2, labeled_images: 0, is_active: true };
  const category = { id: 1, dataset_id: 1, name: '机器人', color: '#ff0000', sort_order: 0 };
  const profile = { id: 1, owner_id: 1, name: '验收接口', endpoint: 'https://example.test/v1', model: 'test', interface_type: 'openai', response_path: 'choices[0].message.content', timeout_seconds: 120, max_attempts: 3 };
  const image = { id: 1, dataset_id: 1, filename: 'test.png', width: 640, height: 480, annotation_revision: 0, annotations: [] };
  let fail = null;
  let stream = null;
  const writes = [];
  await page.addInitScript(() => {
    localStorage.removeItem('robomark-token');
    localStorage.removeItem('robomark-user');
    if (!['/login', '/register'].includes(location.pathname)) {
      localStorage.setItem('robomark-token', 'feedback-test-token');
      localStorage.setItem('robomark-user', JSON.stringify({ id: 1, username: '通知验收', is_admin: true, is_active: true }));
    }
  });
  await page.unroute('**/api/**');
  await page.route('**/api/**', async route => {
    const request = route.request(), path = new URL(request.url()).pathname, method = request.method();
    if (!path.startsWith('/api/')) return route.continue();
    if (method !== 'GET') writes.push({ path, method });
    if (fail && (!fail.path || path === fail.path) && (!fail.method || method === fail.method)) {
      if (fail.network) return route.abort('failed');
      return route.fulfill({ status: fail.status || 400, contentType: fail.html ? 'text/html' : 'application/json', body: fail.html || JSON.stringify({ detail: fail.detail || '验收操作失败' }) });
    }
    if (path === '/api/datasets/batch-import') return route.fulfill({ contentType: 'text/event-stream', body: stream || 'data: {"status":"done","message":"导入完成"}\n\n' });
    if (/\/(file|preview)$/.test(path)) return route.fulfill({ contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="480"><rect width="640" height="480" fill="#667788"/></svg>' });
    let data = {};
    if (path === '/api/auth/me') data = user;
    else if (path === '/api/auth/login') data = { access_token: 'feedback-test-token', user };
    else if (path === '/api/auth/register') data = user;
    else if (path === '/api/datasets') data = method === 'GET' ? [dataset] : dataset;
    else if (path === '/api/datasets/1') data = dataset;
    else if (path === '/api/categories/dataset/1') data = [category];
    else if (path === '/api/preannotation/profiles') data = [profile];
    else if (path === '/api/admin/users') data = [user, { ...user, id: 2, username: '验收成员', is_admin: false }];
    else if (path === '/api/export/formats') data = [{ id: 'yolov8', name: 'YOLOv8' }];
    else if (path === '/api/export') data = { format: 'yolov8', total_images: 2, categories: 1, download_url: '/api/export/download/fixture' };
    else if (/preannotation-tasks$/.test(path)) data = { items: [], total: 0 };
    else if (/\/datasets\/1\/images$/.test(path)) data = { items: [], total: 0 };
    else if (/\/images\/next\/1\/batch$/.test(path)) data = [image];
    else if (path === '/api/images/1' || path === '/api/images/next/1') data = image;
    else if (path === '/api/images/dataset/1/progress') data = { total: 2, labeled: 0, pending: 2, skipped: 0, progress: 0 };
    else if (path === '/api/dataset-configs/1') data = { format_type: 'yolo', source_width: 640, source_height: 480 };
    return route.fulfill({ status: 200, json: data });
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  const toast = () => page.locator('[data-sonner-toast][data-type="error"]');
  async function checkToast(text) {
    await toast().filter({ hasText: text }).waitFor();
    if (await toast().count() !== 1) throw new Error('Duplicate error notifications: ' + await toast().allTextContents());
    await toast().hover();
    await toast().getByRole('button', { name: 'Close toast' }).click();
    await toast().waitFor({ state: 'detached' });
  }
  async function visit(path) { fail = null; await page.goto('http://127.0.0.1:5173' + path); }

  await visit('/login');
  await page.getByRole('textbox', { name: '用户名', exact: true }).fill('invalid-user');
  await page.getByRole('textbox', { name: '密码', exact: true }).fill('invalid-password');
  fail = { path: '/api/auth/login', status: 401, detail: '用户名或密码错误' };
  await page.getByRole('button', { name: '登录工作空间' }).click();
  await checkToast('用户名或密码错误');
  if (new URL(page.url()).pathname !== '/login' || await page.getByRole('textbox', { name: '用户名', exact: true }).inputValue() !== 'invalid-user') throw new Error('Login reloaded or lost input');
  await page.getByRole('alert').filter({ hasText: '用户名或密码错误' }).waitFor();
  await page.screenshot({ path: 'output/playwright/feedback-login.png', fullPage: true });
  results.push('登录401：单次通知、持久错误、保留输入');
  fail = { path: '/api/auth/login', network: true };
  await page.getByRole('button', { name: '登录工作空间' }).click();
  await checkToast('无法连接服务器');
  fail = { path: '/api/auth/login', status: 400, detail: '用户已被禁用' };
  await page.getByRole('button', { name: '登录工作空间' }).click();
  await checkToast('用户已被禁用');
  results.push('登录断网、账号禁用均通知且允许重试');

  await visit('/register');
  await page.getByRole('textbox', { name: '用户名', exact: true }).fill('existing-user');
  await page.getByRole('textbox', { name: '密码', exact: true }).fill('password123');
  await page.getByRole('textbox', { name: '确认密码', exact: true }).fill('password123');
  fail = { path: '/api/auth/register', status: 400, detail: '用户名已存在' };
  await page.getByRole('button', { name: '创建账号', exact: true }).click();
  await checkToast('用户名已存在');
  results.push('注册400通知');

  await visit('/admin/datasets');
  await page.getByRole('button', { name: '新建数据集', exact: true }).click();
  await page.getByRole('textbox', { name: '名称', exact: true }).fill('新数据集');
  await page.getByRole('textbox', { name: '图片目录', exact: true }).fill('/test/images');
  fail = { path: '/api/datasets', method: 'POST', status: 422, detail: [{ msg: '目录格式不正确' }] };
  await page.getByRole('dialog').getByRole('button', { name: '确定', exact: true }).click();
  await checkToast('目录格式不正确');
  await page.getByRole('dialog').getByRole('button', { name: '取消', exact: true }).click();
  results.push('创建数据集422通知');

  await page.getByRole('button', { name: '批量导入', exact: true }).click();
  await page.getByRole('textbox', { name: '根目录', exact: true }).fill('/test');
  fail = { path: '/api/datasets/batch-import', status: 403, detail: '没有目录访问权限' };
  await page.getByRole('button', { name: '开始导入', exact: true }).click();
  await checkToast('没有目录访问权限');
  await page.locator('.progress-message').filter({ hasText: '没有目录访问权限' }).waitFor();
  fail = null;
  stream = 'data: {"status":"importing","message":"正在导入"}\n\n';
  await page.getByRole('button', { name: '开始导入', exact: true }).click();
  await checkToast('导入连接中断');
  stream = 'data: {"status":"error","message":"磁盘已满"}\n\n';
  await page.getByRole('button', { name: '开始导入', exact: true }).click();
  await checkToast('磁盘已满');
  results.push('批量导入403、流中断、服务端进度错误均通知');

  await visit('/admin/categories/1');
  await page.getByRole('heading', { name: '机器人', exact: true }).waitFor();
  fail = { path: '/api/categories/1/template-image', status: 413, detail: '模板文件太大' };
  await page.locator('input[type=file]').first().setInputFiles({ name: 'template.png', mimeType: 'image/png', buffer: Buffer.from('test') });
  await checkToast('模板文件太大');
  results.push('模板上传413保留后端错误且仅通知一次');

  await visit('/datasets/1/settings');
  await page.getByRole('textbox', { name: '数据集名称', exact: true }).waitFor();
  fail = { path: '/api/datasets/1', method: 'PUT', status: 500, html: '<html>Internal Server Error</html>' };
  await page.getByRole('button', { name: '保存设置', exact: true }).click();
  await checkToast('服务器处理失败');
  results.push('设置保存500通知');

  await visit('/profiles');
  await page.getByRole('button', { name: '测试连接', exact: true }).waitFor();
  fail = { path: '/api/preannotation/profiles/1/test', status: 502, detail: '推理服务暂时不可用' };
  await page.getByRole('button', { name: '测试连接', exact: true }).click();
  await checkToast('推理服务暂时不可用');
  results.push('接口测试502通知');

  await visit('/admin/export');
  await page.getByRole('button', { name: '选择数据集', exact: true }).click();
  await page.getByRole('option', { name: /验收数据集/ }).click();
  await page.getByRole('button', { name: '开始导出' }).click();
  await page.getByRole('button', { name: '下载 ZIP 文件' }).waitFor();
  fail = { path: '/api/export/download/fixture', status: 404, detail: '导出文件已过期' };
  await page.getByRole('button', { name: '下载 ZIP 文件' }).click();
  await checkToast('导出文件已过期');
  results.push('下载Blob错误显示后端原因且不重复通知');

  await visit('/admin/users');
  await page.getByRole('button', { name: '禁用', exact: true }).first().waitFor();
  fail = { path: '/api/admin/users/1', method: 'PUT', status: 403, detail: '不能禁用当前管理员' };
  await page.getByRole('button', { name: '禁用', exact: true }).first().click();
  await checkToast('不能禁用当前管理员');
  results.push('用户管理403通知');

  await visit('/annotate/1?source=manual&image=1');
  await page.locator('canvas').waitFor();
  fail = { path: '/api/images/1/save', status: 409, detail: '标注版本冲突，请刷新后重试' };
  await page.keyboard.press('Control+s');
  await checkToast('标注版本冲突');
  results.push('标注保存409只通知一次，保留当前图片');
  if (!page.url().includes('image=1')) throw new Error('Failed save changed the active image');

  // A failed foreground request uses the same global notification mechanism on every page.
  for (const status of [400, 403, 404, 409, 413, 422, 429, 500, 502, 503]) {
    fail = { path: '/api/feedback-check', status, detail: `错误状态${status}` };
    await page.evaluate(async () => { const { default: api } = await import('/src/utils/api.js'); try { await api.get('/feedback-check'); } catch {} });
    await checkToast(`错误状态${status}`);
  }
  results.push('通用请求层10种HTTP失败状态均通知');

  fail = { path: '/api/auth/me', status: 503, detail: '用户服务暂不可用' };
  await page.evaluate(async () => { const { useUserStore } = await import('/src/stores/user.js'); try { await useUserStore().fetchUser(); } catch {} });
  await checkToast('用户服务暂不可用');
  if (!await page.evaluate(() => !!localStorage.getItem('robomark-token'))) throw new Error('Transient failure cleared credentials');
  results.push('用户信息503保留登录状态');
  fail = { path: '/api/feedback-check', status: 401 };
  await page.evaluate(async () => { const { default: api } = await import('/src/utils/api.js'); await Promise.allSettled([api.get('/feedback-check'), api.get('/feedback-check')]); });
  await checkToast('登录状态已失效');
  await page.waitForURL(/\/login\?redirect=/);
  if (await page.evaluate(() => localStorage.getItem('robomark-token') || localStorage.getItem('robomark-user'))) throw new Error('Expired credentials remain');
  if (!new URL(page.url()).searchParams.get('redirect')?.startsWith('/annotate/1')) throw new Error('Return location lost');
  results.push('并发401单次通知、清除会话、保留返回地址');
  if (errors.length) throw new Error('Unhandled browser errors: ' + errors.join('; '));
  return { passed: results.length, results, unhandledErrors: errors, mockedWrites: writes.length };
}
