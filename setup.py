from os import path
from setuptools import setup

here = path.abspath(path.dirname(__file__))
long_description = None

# Get the long description from the README file
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='httpsrv',
    version='0.1.4',
    description='Simple http server for API mocking during automated testing',
    long_description=long_description,
    url='https://github.com/nyrkovalex/httpsrv',
    author='Alexander Nyrkov',
    author_email='nyrkovalex@gmail.com',
    license='MIT',
    packages=['httpsrv'],

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Testing',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],
    keywords='api http mock testing',
    extras_require={
        'test': ['requests'],
    },
)
