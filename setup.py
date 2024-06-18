import pathlib
from setuptools import find_packages, setup

__version__ = "0.0.3"

pwd = pathlib.Path(__file__).parent
requirements_file = pathlib.Path(pwd, "requirements.txt")
install_requires = requirements_file.read_text().splitlines()

setup(
    name='vlab',
    version=__version__,
    packages=find_packages(),
    url='https://github.com/omaxx/vlab',
    license='MIT',
    author='Maxim Orlov',
    author_email='maxx.orlov@gmail.com',
    description='',
    entry_points={
        "console_scripts": [
            "vlab=vlab:cli",
        ]
    },
    install_requires=install_requires,
)
