"""Regenerate runtime templates from the annotated ok_templates submodule."""

from pathlib import Path

from ok.feature.FeatureSet import compress_copy_coco


def main():
    root = Path(__file__).resolve().parent
    source = root / 'ok_templates'
    if not (source / 'coco_annotations.json').is_file():
        raise FileNotFoundError('Initialize the ok_templates submodule before exporting assets')
    compress_copy_coco(str(source / 'coco_annotations.json'), str(root / 'assets'), str(source))


if __name__ == '__main__':
    main()
