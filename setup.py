from setuptools import setup

setup(
    name='lightkube',
    version="0.0.1",
    description='Lightweight kubernetes client library',
    long_description='Lightweight kubernetes client library',
    author='Giuseppe Tribulato',
    author_email='gtsystem@gmail.com',
    license='Apache Software License',
    url='https://github.com/gtsystem/lightkube',
    packages=['lightkube', 'lightkube.config', 'lightkube.core'],
    install_requires=[
        'lightkube-models',
        'httpx >= 0.14.1',
        'respx',
        'PyYAML'
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8'
    ]
)
