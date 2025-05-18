from setuptools import setup
from pathlib import Path

setup(
    name='lightkube',
    version="0.17.2",
    description='Lightweight kubernetes client library',
    long_description=Path("README.md").read_text(),
    long_description_content_type="text/markdown",
    author='Giuseppe Tribulato',
    author_email='gtsystem@gmail.com',
    license='MIT',
    url='https://github.com/gtsystem/lightkube',
    packages=['lightkube', 'lightkube.config', 'lightkube.core', 'lightkube.utils'],
    package_data={'lightkube': ['py.typed']},
    install_requires=[
        'lightkube-models >= 1.15.12.0',
        'httpx >= 0.28.1, < 1.0.0',
        'PyYAML'
    ],
    extras_require={
        "dev": [
            "pytest",
            "pytest-asyncio",
            "respx"
        ]
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13'
    ]
)
