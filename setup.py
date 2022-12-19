from setuptools import setup
from pathlib import Path

setup(
    name='lightkube',
    version="0.12.0",
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
        'httpx >= 0.20.0',
        'PyYAML',
        'backports-datetime-fromisoformat;python_version<"3.7"',
        'dataclasses;python_version<"3.7"'
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11'
    ]
)
