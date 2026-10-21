async (page) => {
  const base = 'http://127.0.0.1:8766/docs/ui-redesign/';
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.goto(base + '#home');
  await page.reload();
  const pages = await page.evaluate(() => prototypePages.map(({id,title,path,group}) => ({id,title,path,group})));
  const results = [];
  for (const viewport of [{width:1600,height:1100},{width:768,height:1024},{width:390,height:844}]) {
    await page.setViewportSize(viewport);
    for (const p of pages) {
      await page.evaluate(id => { location.hash=id; }, p.id);
      await page.waitForFunction(id => document.body.dataset.page === id, p.id);
      await page.evaluate(async () => {
        await document.fonts.ready;
        document.querySelectorAll('img').forEach(img=>img.loading='eager');
        await Promise.all(Array.from(document.images).map(img => img.complete ? Promise.resolve() : new Promise(resolve => { img.onload=resolve; img.onerror=resolve; })));
      });
      const check = await page.evaluate(() => ({
        overflow:document.documentElement.scrollWidth > innerWidth,
        width:document.documentElement.scrollWidth,
        height:Math.max(innerHeight,document.documentElement.scrollHeight),
        brokenImages:Array.from(document.images).filter(i=>!i.complete||!i.naturalWidth).map(i=>i.src),
        empty:!document.querySelector('#app').textContent.trim(),
        badLinks:Array.from(document.querySelectorAll('a[href^="#"]')).filter(a=>!prototypePages.some(p=>p.id===a.hash.slice(1))&&!['trace','prompts'].includes(a.hash.slice(1))).map(a=>a.hash)
      }));
      const screenshot = viewport.width===1600 ? `docs/ui-redesign/screenshots/full-site/${p.id}.jpg` : `output/playwright/ui-redesign-full/${p.id}-${viewport.width}.png`;
      await page.screenshot({path:screenshot,fullPage:true,...(viewport.width===1600?{type:'jpeg',quality:85}:{})});
      results.push({id:p.id,viewport:viewport.width,...check});
    }
  }
  const scenes = [
    {id:'history-dialog',title:'数据集历史 Prompt · 弹窗',host:'preannotation',path:'当前数据集 / 历史记录',group:'弹窗与状态',action:'prompt'},
    {id:'trace-dialog',title:'图像推理详情 · 弹窗',host:'preannotation',path:'批次结果 / 推理详情',group:'弹窗与状态',action:'trace'},
    {id:'category-dialog',title:'多快捷键与图片模板 · 弹窗',host:'categories',path:'类别 / 编辑与模板导入',group:'弹窗与状态',action:'category'},
    {id:'quick-category-dialog',title:'画后快捷选类别 · 弹窗',host:'annotate',path:'工作台 / 绘制后选择类别',group:'弹窗与状态',action:'quick'},
    {id:'export-ready',title:'导出预览 · 生成后',host:'export',path:'数据导出 / 提交配置后',group:'弹窗与状态',action:'export'}
  ];
  await page.setViewportSize({width:1600,height:1100});
  for (const scene of scenes) {
    await page.evaluate(id=>location.hash=id,scene.host);
    await page.waitForFunction(id=>document.body.dataset.page===id,scene.host);
    if(scene.action==='prompt')await page.locator('[data-action="prompt-history"]').click();
    if(scene.action==='trace')await page.locator('.result-card [data-action="trace"]').first().click();
    if(scene.action==='category')await page.locator('[data-edit-category="0"]').first().click();
    if(scene.action==='quick')await page.evaluate(()=>{wb.category=null;wbPickCategory({x:20,y:20,w:15,h:18,shape:'rect'})});
    if(scene.action==='export')await page.getByRole('button',{name:'预览导出结果',exact:true}).click();
    await page.screenshot({path:`docs/ui-redesign/screenshots/full-site/${scene.id}.jpg`,type:'jpeg',quality:85,fullPage:true});
    pages.push({...scene,target:scene.host});
    if(await page.locator('#modal').evaluate(d=>d.open))await page.keyboard.press('Escape');
  }
  return {pages,results,errors};
}
