"""复用当前助手的截图与 OCR，不启动另一套助手或下载模型。"""
from datetime import datetime, timezone
from pathlib import Path
import time


def collect_page(port, game, identity, calibration_path, timeout_seconds, *,
                 probe, folder, guard, clock=time.monotonic, pause=time.sleep, selected_ids=None):
    import cv2
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 90:
        raise ValueError('库存读取时间须为1至90秒')
    cfg = probe.load_calibration(Path(calibration_path), game)
    if selected_ids is not None:
        if not isinstance(selected_ids, list) or len(selected_ids) != 1:
            raise ValueError('每次只读取一个已选材料')
        cfg = dict(cfg, materials=[row for row in cfg['materials'] if row['id'] == selected_ids[0]])
        if len(cfg['materials']) != 1:
            raise ValueError('已选材料未在当前识别配方中唯一定位')
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    deadline = clock() + timeout_seconds
    frames = []

    def check():
        guard()
        probe.check_calibration_sources(cfg)
        if clock() >= deadline:
            raise TimeoutError('库存读取超时，未识别数量不当作0')

    def read(roi, native):
        check()
        token = port._read(roi, native)
        check()
        return token

    def matches(token, name):
        return (isinstance(token, dict) and probe.compact(token.get('text', '')) == probe.compact(name)
                and type(token.get('confidence')) in (int, float)
                and .9 <= token['confidence'] <= 1)

    for sample in range(8):
        check()
        native = port._frame()
        when = datetime.now(timezone.utc).isoformat()
        if not matches(read(cfg['page_anchor']['roi'], native), cfg['page_anchor']['text']):
            pause(.15)
            continue
        stock = cfg.get('stock_anchor')
        if stock and not matches(read(stock['roi'], native), stock['text']):
            pause(.15)
            continue
        image = cv2.resize(native, (1920, 1080))
        index = len(frames)
        frame = dict(game=game, source='native-bag-ocr', frame_id=f'{index}-{when}',
                     captured_at=when, evidence=str(folder), items=[], page_verified=True)
        for number, item in enumerate(cfg['materials']):
            label = read(item['label_roi'], native)
            count = read(item['quantity_roi'], native)
            if not matches(label, item['name']) or not isinstance(count, dict):
                continue
            proofs = []
            for kind, roi_key in (('label', 'label_roi'), ('quantity', 'quantity_roi')):
                check()
                x, y, w, h = item[roi_key]
                file = folder / f'frame-{index}-item-{number}-{kind}.png'
                if not cv2.imwrite(str(file), image[y:y+h, x:x+w]):
                    raise RuntimeError('库存截图保存失败')
                proofs.append(dict(path=str(file), sha256=probe.file_sha256(file)))
            frame['items'].append(dict(id=item['id'], bound_label=item['name'],
                label_roi=item['label_roi'], quantity_roi=item['quantity_roi'],
                label_confidence=label['confidence'], quantity_confidence=count.get('confidence'),
                quantity_text=count.get('text'), crop_evidence=proofs))
        frames.append(frame)
        if len(frames) == 2:
            break
        pause(.2)
    check()
    result = probe.observation.report(game, cfg['materials'], frames)
    result.update(game_identity=dict(identity), game_exe_sha256=cfg['game_exe_sha256'],
                  resource_fingerprints=cfg['resource_fingerprints'],
                  inventory_coverage=cfg['scope'], page_verified_twice=probe.verified_pair(frames))
    probe.atomic_json(folder / 'frames.json', frames)
    check()
    return result
