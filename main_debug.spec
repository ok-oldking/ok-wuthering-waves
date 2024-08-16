# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import rapidocr_openvino


block_cipher = None

package_name = 'rapidocr_openvino'
install_dir = Path(rapidocr_openvino.__file__).resolve().parent

onnx_paths = list(install_dir.rglob('*.onnx')) + list(install_dir.rglob('*.txt'))
yaml_paths = list(install_dir.rglob('*.yaml'))

onnx_add_data = [(str(v.parent), f'{package_name}/{v.parent.name}')
                 for v in onnx_paths]

yaml_add_data = []
for v in yaml_paths:
    if package_name == v.parent.name:
        yaml_add_data.append((str(v.parent / '*.yaml'), package_name))
    else:
        yaml_add_data.append(
            (str(v.parent / '*.yaml'), f'{package_name}/{v.parent.name}'))

import openvino

block_cipher = None

package_name = 'openvino'
install_dir = Path(openvino.__file__).resolve().parent

openvino_dll_path = list(install_dir.rglob('openvino_intel_cpu_plugin.dll')) + list(install_dir.rglob('openvino_onnx_frontend.dll'))


# Modified list comprehension with a condition check
openvino_add_data = [(str(v), f'{package_name}/{v.parent.name}')
                     for v in openvino_dll_path]

print(f'openvino_add_data {openvino_add_data}')
add_data = list(set(yaml_add_data + onnx_add_data + openvino_add_data))

excludes = ['FixTk', 'tcl', 'tk', '_tkinter', 'tkinter', 'Tkinter', 'resources', 'matplotlib','numpy.lib']
add_data.append(('icon.ico', '.'))

import ok
ok_dir = Path(ok.__file__).resolve().parent
binaries = os.path.join(ok_dir, 'binaries', '*')
print(f'ok_dir {ok_dir}')
add_data.append((binaries, 'ok/binaries'))

def list_files(directory, prefix=''):
    file_list = []
    for root, dirs, files in os.walk(directory):
        for filename in files:
            # Create the full filepath by joining root with the filename
            filepath = os.path.join(root, filename)
            # Create the relative path for the file to be used in the spec datas
            relative_path = os.path.relpath(filepath, prefix)
            folder_path = os.path.dirname(relative_path)
            # Append the tuple (full filepath, relative path) to the file list
            file_list.append((filepath, folder_path))
    return file_list

if os.path.exists('assets'):
    root_folder = os.getcwd()  # Get the current working directory
    assets = list_files(os.path.join(root_folder, 'assets'), root_folder)
    add_data += assets

print(f"add_data {add_data}")

a = Analysis(
    ['main_debug.py'],
    pathex=[],
    binaries=[],
    datas=add_data,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
    noconsole=True,
)


# List of patterns to exclude
exclude_patterns = ['opencv_videoio_ffmpeg',  'opengl32sw.dll', 'Qt6Quick.dll','Qt6Pdf.dll','Qt6Qml.dll','Qt6OpenGL.dll','Qt6Network.dll','Qt6QmlModels.dll','Qt6VirtualKeyboard.dll','QtNetwork.pyd'
,'openvino_pytorch_frontend.dll','openvino_tensorflow_frontend.dll','py_tensorflow_frontend.cp311-win_amd64.pyd','py_pytorch_frontend.cp311-win_amd64.pyd',
]


# Optimized list comprehension using any() with a generator expression
a.binaries = [x for x in a.binaries if not any(pattern in x[0] for pattern in exclude_patterns)]

print(f'a.binaries {a.binaries}')

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ok-baijing',
    icon='icon.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='bundle',
)

