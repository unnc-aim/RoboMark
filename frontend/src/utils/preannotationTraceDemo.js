// 仅用于带有 demo=1 标识的交互示例；不请求推理接口、不写入数据库。
export function createTraceDemo(datasetId, taskId, imageId, scenario='success') {
  const image={id:imageId,dataset_id:datasetId,filename:'shapes_03_two_shapes.png',width:960,height:640}
  const categories=[{id:1,name:'矩形',color:'#e76550'},{id:2,name:'圆形',color:'#20a77b'}]
  const annotations=[{category_id:1,annotation_type:'bbox',x_center:.2708,y_center:.4766,width:.3542,height:.3906},
    {category_id:2,annotation_type:'bbox',x_center:.75,y_center:.4844,width:.2708,height:.4063}]
  const input={prompt:'标注图片中的所有矩形和圆形，框住完整边界。',model:'vision-model-demo',
    endpoint:'http://inference.example/v1/chat/completions',interface_type:'openai',annotation_type:'bbox',categories,
    conversion:{response_path:'choices[0].message.content',annotations_path:'annotations',coordinate_system:'normalized',box_format:'center'}}
  const stage=(data,offset=0)=>({at:new Date(Date.now()-2400+offset).toISOString(),data})
  const request=stage({method:'POST',endpoint:input.endpoint,headers:{'Content-Type':'application/json',Authorization:'[已隐藏]'},
    prompt:input.prompt,image:{filename:image.filename,width:960,height:640,bytes:14009,mime:'image/png'},
    body:{model:input.model,messages:[{role:'system',content:'仅输出匹配当前类别与标注 Schema 的 JSON。'},
      {role:'user',content:[{type:'text',text:input.prompt},{type:'image_url',image_url:{url:'[图片内容，见原图]'}}]}]},
    conversion:input.conversion,output_schema:{type:'object',properties:{annotations:{type:'array'}}}})
  const first={id:1,sequence_number:1,status:'failed',elapsed_ms:1320,error_code:'http',error_message:'推理服务返回 HTTP 502',
    trace:{request,response_headers:stage({http_status:502}),response:stage({http_status:502,raw:'{"error":{"message":"服务暂时不可用，请重试"}}'})}}
  const raw={choices:[{message:{content:JSON.stringify({annotations}),reasoning_content:'示例：左侧是矩形，右侧是圆形；分别生成贴合边界的矩形框。'},finish_reason:'stop'}],usage:{prompt_tokens:1120,completion_tokens:168,total_tokens:1288}}
  const second={id:2,sequence_number:2,status:scenario==='running'?'running':'succeeded',elapsed_ms:2340,
    trace:{request,response_headers:stage({http_status:200,content_type:'application/json',request_id:'demo-request-002'},100)}}
  if(scenario!=='running') Object.assign(second.trace,{response:stage({raw:JSON.stringify(raw),http_status:200,bytes:560},2200),
    parsed:stage({output:raw.choices[0].message.content,reasoning_content:raw.choices[0].message.reasoning_content,usage:raw.usage},2300),
    normalized:stage({annotations,count:2},2340)})
  return {image,input,task:{id:taskId,dataset_id:datasetId,status:scenario==='failed'?'failed':scenario==='running'?'running':'completed',prompt:input.prompt},
    task_image:{id:1,execution_status:scenario==='failed'?'failed':scenario==='running'?'running':'succeeded',review_status:'unreviewed',attempts:scenario==='failed'?1:2,
      error_code:scenario==='failed'?'http':null,error_message:scenario==='failed'?first.error_message:null},
    attempts:scenario==='legacy'?[]:scenario==='failed'?[first]:[first,second],total:scenario==='legacy'?0:scenario==='failed'?1:2,
    legacy_response:scenario==='legacy'?JSON.stringify(raw):null,can_retry:scenario==='failed'}
}
