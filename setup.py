from setuptools import setup


setup(
    name="incidentbench",
    version="0.1.0",
    description="Deterministic incident triage and runbook operations environment",
    packages=["server"],
    py_modules=["models", "grader", "client", "inference"],
    install_requires=[
        "fastapi>=0.115.0",
        "uvicorn[standard]>=0.30.0",
        "pydantic>=2.7.0",
        "requests>=2.32.0",
        "openai>=1.40.0",
    ],
    extras_require={
        "dev": [
            "pytest>=8.3.0",
            "httpx>=0.27.0",
        ]
    },
)
