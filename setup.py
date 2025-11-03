from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="brainet",
    version="0.2.2",
    packages=find_packages(exclude=["tests", "tests.*", "docs"]),
    include_package_data=True,
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "brainet=brainet.cli:main"
        ]
    },
    author="Meet Joshi",
    author_email="meetxiv@gmail.com",
    description="AI-powered development context tracker - never lose your train of thought",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/meetxiv/brainet",
    project_urls={
        "Bug Reports": "https://github.com/meetxiv/brainet/issues",
        "Source": "https://github.com/meetxiv/brainet",
        "Documentation": "https://github.com/meetxiv/brainet#readme",
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Version Control :: Git",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Utilities",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
        "Environment :: Console",
    ],
    python_requires=">=3.8",
    keywords="ai development context git productivity claude groq llm developer-tools cli",
    license="MIT",
)