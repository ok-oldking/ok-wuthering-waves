import setuptools
from Cython.Build import cythonize
from distutils.extension import Extension
from setuptools import Extension

import os

os.environ["PYTHONIOENCODING"] = "utf-8"


def find_pyx_packages(base_dir):
    extensions = []
    for dirpath, _, filenames in os.walk(base_dir):
        for filename in filenames:
            if filename.endswith(".pyx"):
                module_path = os.path.join(dirpath, filename).replace('/', '.').replace('\\', '.')
                module_name = module_path[:-4]  # Remove the .pyx extension
                extensions.append(
                    Extension(name=module_name, language="c++", sources=[os.path.join(dirpath, filename)]))
                print(f'add Extension: {module_name} {[os.path.join(dirpath, filename)]}')
    return extensions


def find_packages_with_init_files(base_dir):
    packages = []
    for dirpath, dirnames, filenames in os.walk(base_dir):
        if '__init__.py' in filenames:
            package = dirpath.replace('/', '.').replace('\\', '.')
            packages.append(package)
    return packages


base_dir = "src"
extensions = find_pyx_packages(base_dir)

setuptools.setup(
    name="ok-ww",
    version="0.0.1",
    author="ok-oldking",
    author_email="firedcto@gmail.com",
    description="Automation with Computer Vision for Python",
    url="https://github.com/ok-oldking/ok-script",
    packages=setuptools.find_packages(),
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
    ],
    ext_modules=cythonize(extensions, compiler_directives={'language_level': "3"})
)
