from setuptools import setup, find_packages

setup(
    name='recon',
    version='0.1.0',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'recon=recon.app:main',
        ],
    },
    install_requires=[],
)