/* Dataset-scoped controls and dialogs for the reviewed prototype. */
const demoBatches=[
 {id:24,name:'全量预标注',prompt:0,total:1280,processed:1280,status:'已完成',results:1269,empty:8,failed:3},
 {id:23,name:'抽样验证',prompt:2,total:8,processed:8,status:'已完成',results:7,empty:1,failed:0},
 {id:22,name:'全量预标注',prompt:0,total:1280,processed:384,status:'运行中',results:380,empty:4,failed:0}
];
function currentDataset(){return datasetData[demo.activeDataset]}
function categoryKeys(c){return c.keys||[c.key].filter(Boolean)}
function batchSummary(){const b=demoBatches.find(b=>b.id===demo.batch);return `<div class="batch-summary fix-mark" data-fix="5 · 下拉切换批次"><div class="batch-symbol">${ic('layers')}</div><div><label class="batch-select-label">当前批次<select id="batch-select" aria-label="切换批次">${demoBatches.map(t=>`<option value="${t.id}" ${b.id===t.id?'selected':''}>#${t.id} · ${t.name}</option>`).join('')}</select></label><p>Qwen2.5-VL-7B · 今天 10:12 创建</p></div>${badge(b.status,b.status==='运行中'?'blue':'green')}<div class="progress-block"><div class="spread"><span>${b.processed.toLocaleString()} / ${b.total.toLocaleString()} 张</span><span>${Math.round(b.processed/b.total*100)}%</span></div><div class="progress-line"><i style="width:${b.processed/b.total*100}%"></i></div></div></div>`}
function taskPanel(){return `<section class="panel tasks-panel fix-mark" data-fix="9 · 恢复完整任务管理"><div class="panel-title spread"><h2>任务管理</h2><button class="btn" data-proto="refresh-tasks">${ic('redo')}刷新</button></div>${table(['批次','批次 Prompt','进度','状态','结果 / 空 / 失败','操作'],demoBatches.map(b=>[`<button class="text-link" data-batch="${b.id}">#${b.id} ${b.name}</button>`,`<div class="batch-prompt"><span title="${esc(demo.prompts[b.prompt])}">${esc(demo.prompts[b.prompt])}</span><button class="text-link" data-fill-batch="${b.prompt}">复用</button></div>`,`<div class="table-progress"><div class="progress-line"><i style="width:${b.processed/b.total*100}%"></i></div><span>${Math.round(b.processed/b.total*100)}%</span></div><small>${b.processed} / ${b.total} 张</small>`,badge(b.status,b.status==='运行中'?'blue':b.status==='已取消'?'amber':'green'),`${b.results} / ${b.empty} / ${b.failed}`,`<div class="row task-actions"><button class="text-link" data-batch="${b.id}">查看结果</button><a class="text-link" href="#annotate" data-review-batch="${b.id}">工作台审核</a>${b.status==='运行中'?`<button class="text-link danger" data-cancel-batch="${b.id}">取消</button>`:b.failed?`<button class="text-link" data-retry-batch="${b.id}">重试失败</button>`:''}</div>`]))}</section>`}
function preannotationRevised(){
 let html=preannotation();
 html=html.replace('RoboMaster · 赛场机器人',esc(currentDataset().name));
 html=html.replace('<div class="inference-layout">',taskPanel()+'<div class="inference-layout">');
 html=html.replace(/<div class="batch-summary">[\s\S]*?<div class="result-toolbar"/,batchSummary()+'<div class="result-toolbar"');
 html=html.replace(/<select aria-label="抽样图片数"[\s\S]*?<\/select>/,`<input type="number" min="1" max="${currentDataset().total||1280}" value="${demo.sampleCount}" aria-label="抽样图片数" id="sample-count">`);
 html=html.replace('<div class="spread small" style="color:#7d8797;font-size:10px"><span>抽样图片</span>','<div class="spread small fix-mark sample-field" data-fix="5 · 自定义抽样数量"><label for="sample-count">抽样图片</label>');
 html=html.replace('class="field-label"><label for="prompt"','class="field-label fix-mark" data-fix="8 · 数据集历史 Prompt 弹窗"><label for="prompt"');
 if(demo.promptDraft)html=html.replace(/<textarea id="prompt">[\s\S]*?<\/textarea>/,`<textarea id="prompt">${esc(demo.promptDraft)}</textarea>`);
 if(demo.batch!==24){const b=demoBatches.find(b=>b.id===demo.batch);html=html.replaceAll('1,280',b.total.toLocaleString()).replaceAll('246',String(b.processed)).replaceAll('1,022','0');}
 return html;
}
function directoryField(title,name,value){return field(title,`<div class="directory-picker"><input name="${name}" value="${esc(value)}" required><button type="button" class="btn" data-choose-directory="${name}">${ic('folder')}从电脑选择</button><input hidden type="file" webkitdirectory directory multiple data-directory="${name}" aria-label="选择${title}"></div>`)}
function exportPreview(){const c=demo.exportConfig;if(!c)return '';const dataset=datasetData.find(d=>d.name===c.dataset)||datasetData[0],total=c.unlabeled?dataset.total:dataset.done,train=Math.floor(total*c.train/100),val=Math.floor(total*c.val/100),test=total-train-val,isCoco=c.format==='COCO JSON',isDarknet=c.format==='YOLO Darknet';const tree=isCoco?`${c.output}/\n├── train/  ${train} 张\n├── val/    ${val} 张\n├── test/   ${test} 张\n└── annotations/\n    ├── instances_train.json\n    ├── instances_val.json\n    └── instances_test.json`:isDarknet?`${c.output}/\n├── images/  ${total} 张\n├── labels/\n├── classes.names\n├── train.txt\n├── val.txt\n├── test.txt\n└── dataset.data`:`${c.output}/\n├── images/\n│   ├── train/  ${train} 张\n│   ├── val/    ${val} 张\n│   └── test/   ${test} 张\n├── labels/\n└── data.yaml`;return `<div class="export-summary"><span class="file-symbol">${ic('folder')}</span><div><h3>${esc(c.output)}</h3><p>${esc(c.dataset)} · ${esc(c.format)}</p></div></div><pre class="file-tree">${esc(tree)}</pre><div id="export-result" class="export-result visible">${badge('配置预览已生成','green')}<p>${total} 张图片 · ${demo.categories.length} 个类别<br>训练 / 验证 / 测试：${c.train}% / ${c.val}% / ${c.test}%</p>${btn('download','下载示例配置','download-config')}</div><p class="body-note">原型下载 JSON 配置；生产页面下载训练数据 ZIP。</p>`}
function openPromptDialog(){
 demo.promptQuery='';
 const indices=demo.activeDataset===1?[1]:demo.activeDataset===2?[2]:[0,2];
 modal('历史 Prompt',`<div class="dialog-context">${esc(currentDataset().name)} · 仅显示当前数据集的批次记录</div><label class="search-field dialog-search">${ic('search')}<input id="dataset-prompt-search" type="search" placeholder="搜索当前数据集的 Prompt" aria-label="搜索历史 Prompt"></label><div id="dataset-prompt-list">${indices.map(i=>`<article class="prompt-entry" data-prompt-text="${esc(demo.prompts[i])}"><div class="spread"><h3>批次 #${24-i} · ${i===1?'装甲板检测':'机器人检测'}</h3><span class="tag">${i===0?'最近使用':'历史快照'}</span></div><p>${esc(demo.prompts[i])}</p><div class="spread"><span>Qwen2.5-VL · 示例记录</span><button class="btn primary" data-use-prompt="${i}">填入识别要求</button></div></article>`).join('')}</div>`,btn('close','取消','close-modal'));
 const d=document.querySelector('#modal');d.classList.add('prompt-dialog');d.dataset.fix='8 · 当前数据集的历史 Prompt';
}
function openTraceDialog(){
 const failed=demo.attempt===1,payload=demo.traceTab==='request'?{model:'Qwen2.5-VL-7B-Instruct',temperature:0.1,prompt:demo.prompts[0],image:`frame_${frames[currentFrame].padStart(6,'0')}.jpg`}:demo.traceTab==='raw'?{http_status:failed?502:200,usage:{prompt_tokens:1248,completion_tokens:186},content:failed?'Bad Gateway':{objects:boxes[currentFrame]}}:failed?{error:'此次请求未生成可用候选结果'}:{objects:boxes[currentFrame].map((b,i)=>({category:labels[b.c],bbox:[b.x,b.y,b.w,b.h],confidence:[.98,.96,.94][i]}))};
 modal('图像推理记录',`<div class="dialog-context">${esc(currentDataset().name)} / 批次 #${demo.batch} / frame_${frames[currentFrame].padStart(6,'0')}.jpg</div><div class="trace-layout"><aside><h3>请求历史</h3>${[2,1].map(n=>`<button data-attempt="${n}" class="attempt ${demo.attempt===n?'selected':''}"><strong>第 ${n} 次请求 ${badge(n===2?'成功':'失败',n===2?'green':'amber')}</strong><span>${n===2?'HTTP 200 · 2.4 s':'HTTP 502 · 1.2 s'}</span></button>`).join('')}</aside><section><div class="trace-message"><span class="avatar">LZ</span><div><span class="message-caption">用户输入</span><p>${esc(demo.prompts[0])}</p></div></div><div class="trace-message"><span class="avatar">AI</span><div>${failed?'<div class="error-note">HTTP 502 · Bad Gateway，未产生候选结果。</div>':'<p>模型返回 3 个候选框。</p><div class="trace-metrics">输入 1,248 tokens · 输出 186 tokens · 77.5 TPS</div>'}</div></div><nav class="payload-tabs">${[['output','转换结果'],['request','请求内容'],['raw','原始响应']].map(([id,n])=>`<button data-trace-tab="${id}" class="${demo.traceTab===id?'active':''}">${n}</button>`).join('')}</nav><pre class="payload">${esc(JSON.stringify(payload,null,2))}</pre></section><aside><div class="trace-image"><img src="${arena(frames[currentFrame])}" alt="本次推理图像"></div><dl class="info-list"><dt>图像尺寸</dt><dd>640 × 480 px</dd><dt>接口</dt><dd>本地 vLLM</dd><dt>形状</dt><dd>矩形框</dd></dl></aside></div>`,btn('close','关闭','close-modal'));
 const d=document.querySelector('#modal');d.classList.add('trace-dialog');d.dataset.fix='10 · 在当前页面查看推理详情';
}
function keyChips(){return demo.keys.map((k,i)=>`<span class="key-chip"><kbd>${esc(k)}</kbd><button type="button" data-key-remove="${i}" aria-label="移除快捷键 ${esc(k)}">×</button></span>`).join('')}
function categoryDialog(index=-1){const c=demo.categories[index]||{name:'',keys:[],color:'#679ce0'};demo.keys=[...categoryKeys(c)];demo.keyCapture=false;demo.templateDraft=c.template||null;modal(index<0?'新建类别':'编辑类别',`<form id="category-form" data-index="${index}" class="form-stack">${field('名称',input('name',c.name,'text','required maxlength="32"'))}<div class="fix-mark category-keys" data-fix="6 · 捕获多个快捷键"><span>快捷键</span><div class="key-chips" id="captured-keys">${keyChips()}</div><button class="btn" type="button" data-proto="capture-key">${ic('keyboard')}按下按键添加</button><small id="key-hint">支持多个快捷键与修饰键组合，Esc 取消捕获。</small></div>${field('类别颜色',input('color',c.color,'color'))}<div class="fix-mark template-import" data-fix="6 · 图片模板导入"><label for="template-file">参考图片模板</label><input id="template-file" name="template" type="file" accept="image/*"><div id="template-preview">${c.template?`<img src="${c.template}" alt="当前类别模板">`:'<span class="muted small">未选择图片</span>'}</div></div><button class="btn primary" type="submit">保存类别</button></form>`,'')}
function afterPrototypeRender(){
 document.querySelectorAll('.detail-images img[loading="lazy"]').forEach(img=>{img.dataset.lazy='true'});
 if(['annotate','manual'].includes(route))preloadWorkbench();
}
document.addEventListener('click',async e=>{
 if(e.target.closest('[data-action="sample"]')&&!document.querySelector('#sample-count').reportValidity()){e.preventDefault();e.stopImmediatePropagation();return}
 const element=key=>e.target.closest(`[${key}]`),proto=element('data-proto')?.dataset.proto;
 const card=e.target.closest('.dataset');if(card){demo.activeDataset=+(card.dataset.dataset||0);if(!e.target.closest('a,button,input')){location.hash='dataset-detail';return}}
 if(element('data-image-page')){demo.imagePage=+element('data-image-page').dataset.imagePage;render()}
 if(element('data-choose-directory')){const name=element('data-choose-directory').dataset.chooseDirectory;document.querySelector(`[data-directory="${name}"]`).click()}
 if(element('data-batch')){demo.batch=+element('data-batch').dataset.batch;render()}
 if(element('data-review-batch'))demo.batch=+element('data-review-batch').dataset.reviewBatch;
 if(element('data-fill-batch')){demo.promptDraft=demo.prompts[+element('data-fill-batch').dataset.fillBatch];document.querySelector('#prompt').value=demo.promptDraft;toast('已复用该批次的 Prompt。')}
 if(element('data-cancel-batch')){const batch=demoBatches.find(b=>b.id===+element('data-cancel-batch').dataset.cancelBatch);batch.status='已取消';render();toast('演示任务已取消。')}
 if(element('data-retry-batch')){const b=demoBatches.find(b=>b.id===+element('data-retry-batch').dataset.retryBatch);b.status='运行中';b.processed-=b.failed;b.failed=0;render();toast('失败图片已重新排队 · 演示。')}
 if(proto==='refresh-tasks')toast('任务状态已刷新 · 示例数据。');
 if(proto==='capture-key'){demo.keyCapture=true;document.querySelector('#key-hint').textContent='等待按键…';element('data-proto').focus()}
 if(element('data-key-remove')){demo.keys.splice(+element('data-key-remove').dataset.keyRemove,1);document.querySelector('#captured-keys').innerHTML=keyChips()}
},true);
document.addEventListener('input',e=>{
 if(e.target.id==='prompt')demo.promptDraft=e.target.value;
 if(e.target.id==='sample-count'){demo.sampleCount=+e.target.value;e.target.setCustomValidity(Number.isInteger(demo.sampleCount)&&demo.sampleCount>=1?'':'请输入正整数')}
 if(e.target.id==='dataset-prompt-search'){const q=e.target.value;document.querySelectorAll('#dataset-prompt-list .prompt-entry').forEach(x=>x.hidden=!x.dataset.promptText.includes(q))}
 if(e.target.closest('#export-form')&&demo.exportDone){demo.exportDone=false;document.querySelector('#export-preview').innerHTML='<div class="preview-empty"><p>配置已变更</p><small>请重新点击“预览导出结果”。</small></div>'}
});
document.addEventListener('change',async e=>{
 if(e.target.id==='batch-select'){demo.batch=+e.target.value;resultFilter='pending';render()}
 if(e.target.id==='image-page-size'){demo.imagePageSize=+e.target.value;demo.imagePage=1;render()}
 if(e.target.dataset.directory){const files=[...e.target.files];if(!files.length)return;const name=e.target.dataset.directory,folder=files[0].webkitRelativePath.split('/')[0]||files[0].name;document.querySelector(`[name="${name}"]`).value=folder;document.querySelector('#directory-summary').textContent=`${folder} · ${files.length} 个文件（本机选择）`}
 if(e.target.id==='template-file'&&e.target.files[0]){const f=e.target.files[0];if(!f.type.startsWith('image/'))return toast('请选择图片文件。');const reader=new FileReader();reader.onload=()=>{demo.templateDraft=reader.result;document.querySelector('#template-preview').innerHTML=`<img src="${reader.result}" alt="所选模板">`};reader.readAsDataURL(f)}
});
document.addEventListener('keydown',e=>{
 if(demo.keyCapture&&document.querySelector('#category-form')){e.preventDefault();e.stopImmediatePropagation();if(['Control','Meta','Alt','Shift'].includes(e.key))return;if(e.key!=='Escape'){const key=normalizedKey(e);if(!demo.keys.includes(key))demo.keys.push(key);document.querySelector('#captured-keys').innerHTML=keyChips()}demo.keyCapture=false;document.querySelector('#key-hint').textContent='已捕获；可继续添加其他按键。';return}
 if(e.key==='Enter'&&e.target.matches('.dataset')){demo.activeDataset=+e.target.dataset.dataset;location.hash='dataset-detail'}
},true);
function normalizedKey(e){return [e.ctrlKey?'Ctrl':e.metaKey?'Meta':'',e.altKey?'Alt':'',e.shiftKey?'Shift':'',e.key===' '?'Space':e.key.length===1?e.key.toLowerCase():e.key].filter(Boolean).join('+')}
