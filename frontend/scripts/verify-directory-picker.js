// Run with playwright-cli run-code --filename while scripts.preview_directory_picker:app serves port 8002.
// Dataset/auth APIs are mocked; directory requests exercise the real FastAPI router.
async (page) => {
  page.setDefaultTimeout(10000);
  const results = [], errors = [], fileChoosers = [], writes = [];
  page.on('pageerror', error => errors.push(error.stack || error.message));
  page.on('filechooser', chooser => fileChoosers.push(chooser));
  const rootResponse = await page.request.get('http://127.0.0.1:8002/api/admin/filesystem/directories');
  if (!rootResponse.ok()) throw new Error('Fixture directory API is unavailable');
  const root = (await rootResponse.json()).path;
  const user = { id: 1, username: '目录验收', is_admin: true, is_active: true };
  const dataset = { id: 1, name: '目录验收数据集', image_path: root + '/Alpha/images', label_path: root + '/Alpha/labels', total_images: 0, labeled_images: 0, is_active: true };
  await page.addInitScript(() => {
    localStorage.setItem('robomark-token', 'directory-test-token');
    localStorage.setItem('robomark-user', JSON.stringify({ id: 1, username: '目录验收', is_admin: true, is_active: true }));
  });
  await page.unroute('**/api/**');
  await page.route('**/api/**', async route => {
    const request = route.request(), url = new URL(request.url());
    if (!url.pathname.startsWith('/api/')) return route.continue();
    if (request.method() !== 'GET') writes.push({ path: url.pathname, method: request.method() });
    if (url.pathname === '/api/admin/filesystem/directories') {
      const response = await route.fetch({ url: 'http://127.0.0.1:8002' + url.pathname + url.search });
      return route.fulfill({ response });
    }
    let data = {};
    if (url.pathname === '/api/auth/me') data = user;
    else if (url.pathname === '/api/datasets') data = [dataset];
    else if (url.pathname === '/api/datasets/1') data = dataset;
    else if (url.pathname === '/api/datasets/1/images') data = { items: [], total: 0 };
    else if (url.pathname === '/api/categories/dataset/1') data = [];
    else if (url.pathname === '/api/dataset-configs/1') data = { format_type: 'dji_roco', annotation_path: root + '/Alpha', source_width: 640, source_height: 480 };
    return route.fulfill({ json: data });
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('http://127.0.0.1:5173/admin/datasets?create=1');
  const form = page.getByRole('dialog', { name: '创建数据集', exact: true });
  await form.getByRole('button', { name: '选择服务器图片目录', exact: true }).click();
  const picker = page.getByRole('dialog', { name: '选择服务器图片目录', exact: true });
  const current = () => picker.locator('.directory-selection strong');
  const waitPath = async path => {
    await page.waitForFunction(value => [...document.querySelectorAll('.directory-selection strong')].some(node => node.textContent === value), path);
  };
  await waitPath(root);
  if (await picker.getByRole('option', { name: 'notes.txt', exact: true }).count()) throw new Error('Files leaked into the directory list');
  if (await picker.getByRole('option', { name: '.hidden', exact: true }).count()) throw new Error('Hidden directory shown by default');
  await page.screenshot({ path: 'output/playwright/server-directory-desktop.png', fullPage: true });
  await picker.getByRole('option', { name: 'Alpha', exact: true }).click();
  await waitPath(root + '/Alpha');
  await picker.getByRole('listbox', { name: '服务器子目录' }).focus();
  await page.keyboard.press('End');
  await page.keyboard.press('Enter');
  await waitPath(root + '/Alpha/labels');
  await picker.getByText('此目录没有可浏览的子目录，可直接选择当前目录', { exact: true }).waitFor();
  await picker.getByRole('button', { name: '选择此目录', exact: true }).click();
  if (await form.getByRole('textbox', { name: '图片目录', exact: true }).inputValue() !== root + '/Alpha/labels') throw new Error('Absolute server path was not returned');
  results.push('服务器目录导航、键盘选择、空目录、完整路径回填');

  await form.getByRole('button', { name: '选择服务器图片目录', exact: true }).click();
  await waitPath(root + '/Alpha/labels');
  await picker.getByRole('button', { name: '上一级', exact: true }).click();
  await waitPath(root + '/Alpha');
  await picker.getByRole('button', { name: '取消', exact: true }).click();
  if (await form.getByRole('textbox', { name: '图片目录', exact: true }).inputValue() !== root + '/Alpha/labels') throw new Error('Cancel modified the form');
  await form.waitFor();
  results.push('重新打开从当前路径开始；取消保留原值和外层弹窗');

  await form.getByRole('button', { name: '选择服务器标签目录', exact: true }).click();
  const labels = page.getByRole('dialog', { name: '选择服务器标签目录', exact: true });
  await labels.getByRole('option', { name: 'Big', exact: true }).waitFor();
  await labels.getByRole('checkbox', { name: '显示隐藏目录' }).check();
  await labels.getByRole('option', { name: '.hidden', exact: true }).waitFor();
  await labels.getByRole('textbox', { name: '筛选子目录' }).fill('中文');
  await labels.getByRole('option', { name: '中文 目录', exact: true }).waitFor();
  await page.waitForFunction(() => document.querySelectorAll('.directory-entry').length === 1);
  await labels.getByRole('option', { name: '中文 目录', exact: true }).click();
  await page.waitForFunction(value => [...document.querySelectorAll('.directory-selection strong')].some(node => node.textContent === value), root + '/中文 目录');
  await labels.getByRole('button', { name: '浏览根目录', exact: true }).click();
  await labels.getByRole('option', { name: 'Big', exact: true }).click();
  await labels.getByRole('option', { name: 'folder-099', exact: true }).waitFor();
  await labels.getByRole('button', { name: '下一页', exact: true }).click();
  await labels.getByRole('option', { name: 'folder-100', exact: true }).waitFor();
  if (await labels.getByRole('option').count() !== 100) throw new Error('Pagination returned the wrong page');
  results.push('隐藏目录、中文名称筛选、百项分页');

  const address = labels.getByRole('textbox', { name: '服务器目录地址' });
  await address.fill(root + '/missing');
  await address.press('Enter');
  await labels.getByRole('alert').filter({ hasText: '服务器目录不存在' }).waitFor();
  if (await labels.getByRole('button', { name: '选择此目录', exact: true }).isEnabled()) throw new Error('Failed path remains selectable');
  const toast = page.locator('[data-sonner-toast][data-type="error"]');
  await toast.filter({ hasText: '服务器目录不存在' }).waitFor();
  await toast.hover();
  await toast.getByRole('button', { name: 'Close toast' }).click();
  await labels.waitFor();
  await address.fill(root + '/Denied');
  await labels.getByRole('button', { name: '跳转', exact: true }).click();
  await labels.getByRole('alert').filter({ hasText: '权限' }).waitFor();
  await labels.getByRole('button', { name: '返回浏览根目录', exact: true }).click();
  await labels.getByRole('option', { name: 'Alpha', exact: true }).waitFor();
  await labels.getByRole('button', { name: '取消', exact: true }).click();
  results.push('404和403通知、禁止确认失败目录、错误后恢复浏览');

  // A read arriving after cancel must not mutate the original value or reopen the picker.
  const slow = '**/api/admin/filesystem/directories*';
  const delay = async route => { await new Promise(resolve => setTimeout(resolve, 350)); await route.fallback(); };
  await page.route(slow, delay);
  await form.getByRole('button', { name: '选择服务器标签目录', exact: true }).click();
  await page.getByRole('dialog', { name: '选择服务器标签目录', exact: true }).getByRole('button', { name: '取消', exact: true }).click();
  await page.unroute(slow, delay);
  if (await form.getByRole('textbox', { name: '标签目录', exact: true }).inputValue()) throw new Error('Cancelled browse changed the value');
  await form.getByRole('button', { name: '取消', exact: true }).click();
  await page.getByRole('button', { name: '批量导入', exact: true }).click();
  await page.getByRole('dialog', { name: '批量导入数据集' }).getByRole('button', { name: '选择服务器根目录', exact: true }).click();
  await page.getByRole('dialog', { name: '选择服务器根目录', exact: true }).getByRole('option', { name: 'Alpha', exact: true }).waitFor();
  await page.getByRole('dialog', { name: '选择服务器根目录', exact: true }).getByRole('button', { name: '选择此目录', exact: true }).click();
  if (await page.getByRole('dialog', { name: '批量导入数据集' }).getByRole('textbox', { name: '根目录', exact: true }).inputValue() !== root) throw new Error('Batch import picker did not return server path');
  results.push('取消在途请求及批量导入根目录接入');

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('http://127.0.0.1:5173/datasets/1/settings');
  await page.getByRole('button', { name: '选择服务器标注来源目录', exact: true }).click();
  const source = page.getByRole('dialog', { name: '选择服务器标注来源目录', exact: true });
  await source.getByRole('option', { name: 'images', exact: true }).waitFor();
  await page.screenshot({ path: 'output/playwright/server-directory-mobile.png' });
  const box = await source.boundingBox();
  if (!box || box.width > 390 || box.x < 0 || box.y < 0 || box.y + box.height > 844) throw new Error('Mobile picker overflows the viewport: ' + JSON.stringify(box));
  await source.getByRole('button', { name: '取消', exact: true }).click();
  if (await page.getByRole('textbox', { name: '标注来源目录', exact: true }).inputValue() !== root + '/Alpha') throw new Error('Settings value changed on cancel');
  results.push('设置页标注来源入口和手机视口布局');
  if (fileChoosers.length || writes.length || errors.length) throw new Error(JSON.stringify({ fileChoosers: fileChoosers.length, writes, errors }));
  return { passed: results.length, results, fileChoosers: fileChoosers.length, writes, unhandledErrors: errors };
}
