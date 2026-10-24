from src.inventory_support.runtime import inventory_root, import_support, valid_game_path
from src.inventory_support.inventory_native_capture import collect_page as collect_native_page
"""Offline replay of native item crops and OCR evidence, never game input.

Recomputes confidence/shortage and combines selected pages from one process.
Does not run OCR, make old captures fresh or claim a complete inventory scan.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
from src.inventory_support import inventory_native_probe as probe
observation = probe.observation

def verified_crop(proof, folder, *, stock_anchor=False):
    if not isinstance(proof, dict) or not isinstance(proof.get('path'), str):
        raise ValueError('Crop proof missing')
    file = Path(proof['path']).resolve()
    if file.parent != folder.resolve() or re.fullmatch('frame-[01]-stock-anchor\\.png' if stock_anchor else 'frame-[01]-item-\\d+-(label|quantity)\\.png', file.name) is None or (not file.is_file()) or (not 8 <= file.stat().st_size <= 1024 * 1024):
        raise ValueError('Crop must be a bounded file inside this capture folder')
    digest = proof.get('sha256')
    if not isinstance(digest, str) or re.fullmatch('[a-f0-9]{64}', digest) is None:
        raise ValueError('Crop hash missing')
    data = file.read_bytes()
    if not data.startswith(b'\x89PNG\r\n\x1a\n') or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('Native crop changed or unavailable')

def replay(folder, calibration_file, game, now=None):
    folder = Path(folder)
    now = now or datetime.now(timezone.utc)
    cfg = probe.load_calibration(calibration_file, game)
    original = json.loads((folder / 'report.json').read_text(encoding='utf-8-sig'))
    if original.get('schema') != 'inventory-report/v1' or original.get('scope') != 'inspection_only' or original.get('game') != game or (original.get('game_exe_sha256') != cfg['game_exe_sha256']) or (original.get('resource_fingerprints') != cfg['resource_fingerprints']) or (original.get('inventory_coverage') != 'selected_materials_only') or (original.get('farming_changed') is not False):
        raise ValueError('Native report and calibration version/scope differ')
    if original.get('page_verified_twice') is not True:
        raise ValueError('Native page not verified in two independent captures')
    frames = json.loads((folder / 'frames.json').read_text(encoding='utf-8-sig'))
    if not isinstance(frames, list) or len(frames) != 2:
        raise ValueError('Expected original two native frames')
    for index, frame in enumerate(frames):
        if frame.get('game') != game or frame.get('source') != 'native-bag-ocr':
            raise ValueError('Wrong native frame source')
        if not isinstance(frame.get('frame_id'), str) or not frame['frame_id'].startswith(f'{index}-'):
            raise ValueError('Native frame sequence changed')
        if 'stock_anchor' in cfg:
            expected = probe.stock_anchor(cfg)
            owned = frame.get('stock_anchor')
            if not isinstance(owned, dict) or owned.get('text') != expected['text'] or owned.get('roi') != expected['roi'] or (type(owned.get('confidence')) not in (int, float)) or (not 0.9 <= owned['confidence'] <= 1):
                raise ValueError('Owned-stock label not independently evidenced in this frame')
            verified_crop(owned, folder, stock_anchor=True)
            if Path(owned['path']).name != f'frame-{index}-stock-anchor.png':
                raise ValueError('Owned-stock anchor belongs to another frame')
        rows = frame.get('items')
        if not isinstance(rows, list) or len(rows) > 128:
            raise ValueError('Unbounded native frame')
        for item in rows:
            proofs = item.get('crop_evidence', [])
            if not isinstance(proofs, list) or len(proofs) != 2:
                raise ValueError('Bound label and quantity crop proofs required')
            if not any((Path(p['path']).name.endswith('-label.png') for p in proofs)) or not any((Path(p['path']).name.endswith('-quantity.png') for p in proofs)):
                raise ValueError('Both distinct crop roles required')
            for proof in proofs:
                verified_crop(proof, folder)
                if not Path(proof['path']).name.startswith(f'frame-{index}-'):
                    raise ValueError('Crop does not belong to this frame')
    result = observation.report(game, cfg['materials'], frames, now)
    if 'recognition_basis' in cfg:
        if original.get('recognition_basis') != cfg['recognition_basis']:
            raise ValueError('Inherited recognition basis changed')
        result['recognition_basis'] = cfg['recognition_basis']
    for key in ('game_identity', 'game_exe_sha256', 'resource_fingerprints', 'inventory_coverage'):
        result[key] = original[key]
    result['reported_at'] = original['reported_at']
    result.update(page_verified_twice=all((frame.get('page_verified') is True for frame in frames)), offline_replayed_at=now.isoformat(), live_capture=False, source_report=str(folder / 'report.json'), source_frames_sha256=hashlib.sha256((folder / 'frames.json').read_bytes()).hexdigest())
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game', choices=('wuwa', 'zzz'), required=True)
    parser.add_argument('--input', nargs=2, action='append', required=True, metavar=('CAPTURE_FOLDER', 'CALIBRATION'))
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    sources = [replay(folder, cfg, args.game, now) for folder, cfg in args.input]
    result = observation.merge_reports(args.game, sources, now)
    result.update(live_capture=False, offline_replayed_at=now.isoformat(), source_paths=[source['source_report'] for source in sources], source_frames_hashes=[source['source_frames_sha256'] for source in sources], evidence_kind='offline_replay_of_previous_native_captures')
    folder = probe.ROOT / 'audits' / datetime.now().strftime('%Y-%m-%d') / 'inventory' / ('replay-' + datetime.now().strftime('%H%M%S-%f'))
    folder.mkdir(parents=True, exist_ok=False)
    probe.atomic_json(folder / 'source-reports.json', sources)
    probe.atomic_json(folder / 'report.json', result)
    print(json.dumps({'report': str(folder / 'report.json'), 'live_capture': False, 'complete_inventory': False, 'confirmed': sum((row['status'] == 'confirmed' for row in result['materials']))}, ensure_ascii=False))
if __name__ == '__main__':
    main()
