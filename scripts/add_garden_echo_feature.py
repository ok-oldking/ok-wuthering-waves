"""向 coco_annotations.json 添加 garden_echo_recommend 特征(声骸推荐标识)。

运行一次: .venv\\Scripts\\python.exe scripts\\add_garden_echo_feature.py
"""
import json
import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[1]
json_path = root / 'assets' / 'coco_annotations.json'
src = root / 'ok_templates' / '35.png'
dst = root / 'assets' / 'images' / '48.png'

data = json.loads(json_path.read_text(encoding='utf-8'))

if not dst.exists():
    shutil.copyfile(src, dst)
    print('copied', dst)

img_id = max(i['id'] for i in data['images']) + 1
data['images'].append({'license': 0, 'url': None, 'file_name': 'images/48.png',
                       'height': 1080, 'width': 1920, 'date_captured': None,
                       'id': img_id})

cat_id = max(c['id'] for c in data['categories']) + 1
data['categories'].append({'id': cat_id, 'name': 'garden_echo_recommend',
                           'supercategory': ''})

ann_id = max(a['id'] for a in data['annotations']) + 1
# 推荐标识(橙色点赞)在 1920x1080 截图上的位置
bbox = [1583, 160, 40, 41]
data['annotations'].append({'id': ann_id, 'image_id': img_id,
                            'category_id': cat_id, 'bbox': bbox,
                            'area': bbox[2] * bbox[3], 'iscrowd': 0})

json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                     encoding='utf-8')
print('done: garden_echo_recommend added')
