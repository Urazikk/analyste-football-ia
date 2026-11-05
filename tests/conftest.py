import pytest

from src import config


@pytest.fixture(autouse=True)
def isolated_dirs(tmp_path, monkeypatch):
    """Traces et état de l'agent dans un dossier temporaire pendant les tests."""
    monkeypatch.setattr(config, "TRACES_DIR", tmp_path / "traces")
    monkeypatch.setenv("STATE_DIR", str(tmp_path / "state"))
