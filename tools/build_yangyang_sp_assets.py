"""Reproduce the user-authorized Yangyang HUD crops; never modify source images."""

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np


SOURCES = [
    '切换羽剑普通E.png', '切换刚剑E.png', '钢剑强化E.png', '羽剑强化E.png',
    '钢剑重击（也就是我说的双圆圈）.png', '羽剑重击1.png',
    '羽剑重击2（实际上就是长按）.png', '羽剑重击3（继续长按）.png',
    '大招亮.png', '正中下方能量条满（可放强化重击）.png',
]

# Reviewed against the original-resolution contact sheet. Exclude animated rings
# and key captions: readiness is measured independently by the runtime detector.
FEATURES = [
    ('yangyang_sp_attack_sword', 0, (2800, 1872, 130, 130)),
    ('yangyang_sp_attack_feather', 1, (2800, 1872, 130, 130)),
    ('yangyang_sp_e_crescent', 2, (3180, 1872, 130, 130)),
    ('yangyang_sp_e_feather', 3, (3180, 1872, 130, 130)),
    ('yangyang_sp_heavy_azure', 4, (2800, 1872, 130, 130)),
    ('yangyang_sp_heavy_air', 6, (2800, 1872, 130, 130)),
    ('yangyang_sp_heavy_followup', 7, (2800, 1872, 130, 130)),
    ('yangyang_sp_liberation', 8, (3562, 1872, 130, 130)),
]


def read_image(path):
    return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)


def write_image(path, image):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(cv2.imencode('.png', image)[1].tobytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--preview', action='store_true')
    args = parser.parse_args()
    frames = [read_image(args.source / name) for name in SOURCES]
    if any(frame is None or frame.shape[:2] != (2159, 3840) for frame in frames):
        raise ValueError('Expected the ten original 3840x2159 screenshots')
    # A contact sheet for coordinate review, with original-resolution HUD pixels.
    rows = []
    for index, frame in enumerate(frames):
        row = frame[1820:2060, 2770:3740].copy()
        cv2.putText(row, str(index), (5, 24), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (0, 255, 255), 2)
        rows.append(row)
    write_image(Path('screenshots/yy_assets_review.png'), np.concatenate(rows))
    if args.preview:
        return
    root = Path(__file__).resolve().parents[1]
    coco_path = root / 'assets/coco_annotations.json'
    coco = json.loads(coco_path.read_text(encoding='utf-8'))
    names = {item[0] for item in FEATURES}
    if names & {cat['name'] for cat in coco['categories']}:
        raise ValueError('Yangyang features already installed; refusing to duplicate annotations')
    category_id = max(cat['id'] for cat in coco['categories']) + 1
    image_id = max(img['id'] for img in coco['images']) + 1
    annotation_id = max(ann['id'] for ann in coco['annotations']) + 1
    manifest = []
    for offset, (name, source, bbox) in enumerate(FEATURES):
        x, y, width, height = bbox
        canvas = np.zeros_like(frames[source])
        canvas[y:y + height, x:x + width] = frames[source][y:y + height, x:x + width]
        filename = f'images/{name}.png'
        write_image(root / 'assets' / filename, canvas)
        coco['images'].append(dict(id=image_id + offset, file_name=filename, width=3840, height=2159))
        coco['categories'].append(dict(id=category_id + offset, name=name, supercategory=''))
        coco['annotations'].append(dict(id=annotation_id + offset, image_id=image_id + offset,
                                        category_id=category_id + offset, bbox=list(bbox),
                                        area=width * height, iscrowd=0, ignore=0, segmentation=[]))
        manifest.append(dict(label=name, source=SOURCES[source], bbox=list(bbox),
                             sha256=hashlib.sha256((args.source / SOURCES[source]).read_bytes()).hexdigest()))
    # Mechanical append to the existing COCO collection, preserving all records.
    coco_path.write_text(json.dumps(coco, ensure_ascii=True, indent=4) + '\n', encoding='utf-8')
    manifest_path = root / 'assets/yangyang_sp_sources.json'
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=True, indent=2) + '\n', encoding='utf-8')
    for index, frame in enumerate(frames):
        write_image(root / f'tests/images/yangyang_sp/hud_{index:02d}.png',
                    frame[1820:2060, 2770:3740])
    print(f'Added {len(FEATURES)} reviewed features and {len(frames)} HUD fixtures')


if __name__ == '__main__':
    main()
