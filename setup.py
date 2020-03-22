from setuptools import setup

with open('README.md') as f:
    README = f.read()

setup(
    name='auTO',
    url='https://github.com/mtimkovich/auTO',
    version='1.3',
    author='Max Timkovich',
    author_email='max@timkovi.ch',
    license='MIT',
    description='A Discord bot for TOing netplay tournaments',
    long_description=README,
    install_requires=[
        'discord.py >= 1.3.2',
        'iso8601',
    ],
    setup_requires=['wheel'],
    python_requires='>=3.7',
    entry_points={'console_scripts': ['auTO=auTO.auTO:main']},
)
