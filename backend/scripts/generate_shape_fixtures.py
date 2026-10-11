"""生成可重复、坐标已知的矩形 / 圆形预标注测试图片。"""
import argparse
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

SCENES = [
    ('single_rectangle', (960,640), '#ffffff', [('rectangle',(220,180,740,460),'#2563eb',False)]),
    ('single_circle', (960,640), '#ffffff', [('circle',(320,160,640,480),'#e45353',False)]),
    ('two_shapes', (960,640), '#f8fafc', [('rectangle',(90,180,430,430),'#ee9b25',False),('circle',(590,180,850,440),'#14a181',False)]),
    ('rectangles', (960,640), '#ffffff', [('rectangle',(60,80,390,210),'#634acb',False),('rectangle',(530,100,850,400),'#2685c1',False),('rectangle',(100,350,380,550),'#dc7350',False)]),
    ('circles', (960,640), '#ffffff', [('circle',(90,100,310,320),'#f97316',False),('circle',(430,300,650,520),'#3b82f6',False),('circle',(720,100,870,250),'#9333ea',False)]),
    ('mixed_colors', (960,640), '#ffffff', [('rectangle',(60,80,330,230),'#dc5050',False),('circle',(440,60,640,260),'#278bb4',False),('rectangle',(730,80,900,340),'#aa70cd',False),('circle',(75,390,255,570),'#cc9821',False),('rectangle',(360,390,610,540),'#18a281',False),('circle',(730,420,870,560),'#e765a4',False)]),
    ('same_color', (960,640), '#ffffff', [('rectangle',(70,80,420,230),'#2563eb',False),('circle',(630,70,840,280),'#2563eb',False),('circle',(90,350,290,550),'#2563eb',False),('rectangle',(460,370,850,550),'#2563eb',False)]),
    ('small_targets', (1280,720), '#ffffff', [('circle',(75,80,111,116),'#e45353',False),('rectangle',(270,120,335,150),'#2563eb',False),('circle',(450,450,500,500),'#14a181',False),('rectangle',(850,280,920,325),'#f97316',False),('circle',(1100,560,1126,586),'#9333ea',False),('rectangle',(650,610,698,632),'#db527e',False)]),
    ('overlapping', (960,640), '#f8fafc', [('rectangle',(150,150,570,380),'#5b8dc4',False),('circle',(390,260,650,520),'#ef8a5b',False),('rectangle',(690,140,900,360),'#8671bd',False),('circle',(670,310,860,500),'#49a786',False)]),
    ('near_edges', (960,640), '#ffffff', [('circle',(5,5,185,185),'#d85858',False),('rectangle',(750,5,955,205),'#258bc1',False),('rectangle',(5,440,330,635),'#ef9d25',False),('circle',(750,430,955,635),'#41a581',False)]),
    ('outlines', (960,640), '#ffffff', [('rectangle',(75,100,420,400),'#2563eb',True),('circle',(570,180,850,460),'#e45353',True)]),
    ('low_contrast_portrait', (640,960), '#eef0f2', [('circle',(80,75,300,295),'#c4c9ce',False),('rectangle',(340,90,580,360),'#c7cdd3',False),('rectangle',(50,490,310,710),'#c5ccd3',False),('circle',(370,650,570,850),'#c5c9ce',False)]),
    ('empty_control', (960,640), '#ffffff', []),
]


def generate(directory, preview):
    directory.mkdir(parents=True, exist_ok=True)
    filenames = [f'shapes_{i:02}_{scene[0]}.png' for i,scene in enumerate(SCENES,1)]
    conflicts = [name for name in [*filenames,'expected_shapes.json','README.md'] if (directory/name).exists()]
    if conflicts:
        raise SystemExit('拒绝覆盖已有文件：'+', '.join(conflicts))
    manifest = {'coordinate_convention':'xyxy pixels, right/bottom exclusive; normalized bbox uses nominal shape bounds',
                'note':'Overlapping shapes use full object bounds. Allow 1–2 pixels for antialiasing.', 'images':[]}
    tiles=[]
    for index, (scenario,size,background,shapes) in enumerate(SCENES,1):
        width,height=size
        factor=4
        image=Image.new('RGB',(width*factor,height*factor),background)
        draw=ImageDraw.Draw(image)
        annotations=[]
        for kind,box,color,outline in shapes:
            x1,y1,x2,y2=box
            if kind=='circle':assert x2-x1==y2-y1
            bounds=(x1*factor,y1*factor,x2*factor-1,y2*factor-1)
            painter=draw.rectangle if kind=='rectangle' else draw.ellipse
            painter(bounds,fill=None if outline else color,outline=color if outline else None,width=6*factor if outline else 1)
            annotations.append({'category_name':kind,'annotation_type':'bbox','bbox_xyxy':list(box),
                'x_center':(x1+x2)/(2*width),'y_center':(y1+y2)/(2*height),'width':(x2-x1)/width,'height':(y2-y1)/height})
        image=image.resize(size,Image.Resampling.LANCZOS)
        filename=filenames[index-1]
        image.save(directory/filename,optimize=True)
        manifest['images'].append({'filename':filename,'scenario':scenario,'width':width,'height':height,'annotations':annotations})
        tile=Image.new('RGB',(280,220),'#f1f5f9')
        thumbnail=image.copy();thumbnail.thumbnail((268,175))
        tile.paste(thumbnail,((280-thumbnail.width)//2,8+(175-thumbnail.height)//2))
        label=f'{index:02} {scenario} | {len(annotations)} targets'
        ImageDraw.Draw(tile).text((8,190),label,fill='#334155',font=ImageFont.load_default())
        tiles.append(tile)
    (directory/'expected_shapes.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    (directory/'README.md').write_text('''# 矩形与圆形测试图片

13 张 PNG：单目标、多目标、多色、同色、小目标、遮挡重叠、靠近边缘、空心轮廓、低对比度与竖图；最后一张为空白对照图。

建议 Prompt：标注图片中的所有矩形和圆形。使用贴合目标边界的外接矩形框，类别对应当前数据集的 rectangle / circle（或矩形 / 圆形），包含空心轮廓的图形。

`expected_shapes.json` 包含每张图的预期类别、像素外接框与归一化坐标，可供人工核对。圆形也使用矩形外接框；遮挡用完整目标边界。此文件不会自动写入正式标注。

重新生成：使用 `backend/scripts/generate_shape_fixtures.py` 的 `--directory` 指定一个空目录；脚本拒绝覆盖现有文件。
''')
    preview.parent.mkdir(parents=True,exist_ok=True)
    sheet=Image.new('RGB',(1120,880),'#e2e8f0')
    for i,tile in enumerate(tiles):sheet.paste(tile,((i%4)*280,(i//4)*220))
    sheet.save(preview,quality=90)
    print(f'Generated {len(filenames)} PNGs with {sum(len(s[3]) for s in SCENES)} targets in {directory}')


if __name__=='__main__':
    root=Path(__file__).resolve().parents[2]
    parser=argparse.ArgumentParser()
    parser.add_argument('--directory',type=Path,default=root/'test')
    parser.add_argument('--preview',type=Path,default=root/'docs/images/preannotation-test-contact-sheet.jpg')
    args=parser.parse_args()
    generate(args.directory,args.preview)
