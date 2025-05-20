from setuptools import setup, find_packages
setup(
    name="agent_ecosystem",
    version="0.1.0",
    packages=find_packages(),
    install_requires=["redis", "streamlit", "jinja2"]
)

