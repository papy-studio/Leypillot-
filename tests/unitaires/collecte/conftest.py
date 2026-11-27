"""Fixtures du lot 1 (les fabriques sont dans ``aide_collecte.py``)."""

from pathlib import Path

import pytest
from aide_collecte import fabriquer_archive_an, fabriquer_archive_jorf


@pytest.fixture
def archive_jorf(tmp_path: Path) -> Path:
    return fabriquer_archive_jorf(tmp_path)


@pytest.fixture
def archive_an(tmp_path: Path) -> Path:
    return fabriquer_archive_an(tmp_path)
