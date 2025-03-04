import os
import sys
import tempfile

import docker
import pytest


@pytest.fixture(name="logprep_container", scope="session")
def get_container() -> docker.models.containers.Container:
    """logprep container fixture to run acceptance tests"""
    client = docker.from_env()
    env = {}
    env.update({"PATH": "/opt/venv/bin:$PATH", "PROMETHEUS_MULTIPROC_DIR": "/tmp/logprep"})
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    container_name = f"pytest-logprep-{python_version}"
    container = client.containers.run(
        f"ghcr.io/fkie-cad/logprep:py{python_version}-main",
        "infinity",
        entrypoint="/usr/bin/sleep",
        name=container_name,
        detach=True,
        environment=env,
        privileged=True,
        working_dir="/logprep",
        volumes={
            os.path.abspath("."): {"bind": "/logprep", "mode": "rw"},
            tempfile.gettempdir(): {"bind": "/tmp", "mode": "rw"},
        },
        ports={"9000/tcp": 9000},
    )
    steps = [
        "pip install .[dev]",
    ]
    for step in steps:
        container.exec_run(step)
    container.stop()
    container.commit(container_name)
    container.remove()

    def runner(config_path, env={}):
        return client.containers.run(
            container_name,
            config_path,
            name=container_name,
            entrypoint="logprep",
            detach=True,
            environment=env,
            privileged=True,
            volumes={
                tempfile.gettempdir(): {"bind": "/tmp", "mode": "rw"},
                os.path.abspath("."): {"bind": "/logprep", "mode": "ro"},
            },
        )

    yield runner
