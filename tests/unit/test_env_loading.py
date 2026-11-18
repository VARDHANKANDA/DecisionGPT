"""Where the backend finds OPENAI_API_KEY. No network, no real secret: every file is a temporary one with a dummy value."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.core import config
from app.core.config import ENV_FILES, Settings

DUMMY = "tsk-DUMMY-NOT-A-REAL-KEY-for-env-loading-tests"
BACKEND = Path(config.__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch):
    for name in ("OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_TIMEOUT_SECONDS", "ANALYTICS_LLM_ENABLED", "ANALYTICS_EXPLAIN_ENABLED"):
        monkeypatch.delenv(name, raising=False)


def write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_env_files_are_absolute_and_independent_of_the_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert all(p.is_absolute() for p in ENV_FILES)
    assert ENV_FILES == (BACKEND.parent / ".env", BACKEND / ".env")  # repo root first, backend/.env last (last one wins)
    assert BACKEND.name == "backend" and (BACKEND / "app" / "core" / "config.py").exists()


def test_the_default_loader_does_not_read_a_dotenv_in_the_current_directory(tmp_path, monkeypatch):
    """The old bare ".env" meant whatever file sat in the cwd. A stray .env there must be ignored now."""
    write(tmp_path / ".env", f"OPENAI_API_KEY={DUMMY}\n")
    monkeypatch.chdir(tmp_path)
    # point the configured files at nothing so only cwd could possibly supply a value
    monkeypatch.setattr(Settings, "model_config", {**Settings.model_config, "env_file": (tmp_path / "missing_a", tmp_path / "missing_b")})
    assert Settings().openai_api_key is None


def test_backend_env_overrides_the_repo_root_env(tmp_path):
    root = write(tmp_path / "root.env", "OPENAI_API_KEY=from-root\nENVIRONMENT=staging\n")
    backend = write(tmp_path / "backend.env", f"OPENAI_API_KEY={DUMMY}\n")
    s = Settings(_env_file=(root, backend))
    assert s.openai_api_key == DUMMY and s.llm_enabled is True
    assert s.environment == "staging"  # unrelated settings from the other file are preserved


def test_a_blank_line_in_one_file_does_not_erase_a_key_set_in_the_other(tmp_path):
    key_file = write(tmp_path / "a.env", f"OPENAI_API_KEY={DUMMY}\n")
    blank_file = write(tmp_path / "b.env", "OPENAI_API_KEY=\nLOG_LEVEL=DEBUG\n")
    for order in ((key_file, blank_file), (blank_file, key_file)):
        s = Settings(_env_file=order)
        assert s.openai_api_key == DUMMY and s.log_level == "DEBUG"


def test_only_blank_values_means_ai_is_off(tmp_path):
    f = write(tmp_path / "x.env", "OPENAI_API_KEY=\n")
    s = Settings(_env_file=(f,))
    assert not s.openai_api_key and s.llm_enabled is False and s.analytics_llm_active is False


def test_a_process_environment_variable_wins_over_the_files(tmp_path, monkeypatch):
    f = write(tmp_path / "x.env", f"OPENAI_API_KEY={DUMMY}\n")
    monkeypatch.setenv("OPENAI_API_KEY", "from-deployment-environment")
    assert Settings(_env_file=(f,)).openai_api_key == "from-deployment-environment"


def test_a_blank_process_variable_still_switches_ai_off(tmp_path, monkeypatch):
    """How a run is told to stay offline (`OPENAI_API_KEY=` in the shell) must keep working even when a file holds a key."""
    f = write(tmp_path / "x.env", f"OPENAI_API_KEY={DUMMY}\n")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    assert Settings(_env_file=(f,)).llm_enabled is False


def test_the_key_is_not_in_the_settings_repr(tmp_path):
    f = write(tmp_path / "x.env", f"OPENAI_API_KEY={DUMMY}\n")
    s = Settings(_env_file=(f,))
    assert DUMMY not in repr(s) and DUMMY not in str(s)


def test_loading_from_another_working_directory_in_a_fresh_interpreter(tmp_path):
    """A real process started elsewhere resolves the same absolute file list (only paths are printed, never a value)."""
    code = "from app.core.config import ENV_FILES; print('|'.join(str(p) for p in ENV_FILES))"
    env = {**os.environ, "PYTHONPATH": str(BACKEND), "OPENAI_API_KEY": ""}
    out = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip().split("|") == [str(p) for p in ENV_FILES]


def test_env_files_are_excluded_from_git_and_from_docker_images():
    root = BACKEND.parent
    gitignore = (root / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in [l.strip() for l in gitignore]  # a bare pattern matches at any depth (backend/.env too)
    dockerignore = [l.strip() for l in (root / ".dockerignore").read_text(encoding="utf-8").splitlines()]
    assert "**/.env" in dockerignore  # `COPY backend ./backend` would otherwise bake backend/.env into the image


# ------------------------------------------------------------------ ANALYTICS_EXPLAIN_ENABLED
@pytest.mark.parametrize("raw", ["false", "False", "FALSE", "0", "no", "off"])
def test_analytics_explain_enabled_false_is_read_from_the_backend_env_file(tmp_path, raw):
    f = write(tmp_path / "b.env", f"OPENAI_API_KEY={DUMMY}\nANALYTICS_EXPLAIN_ENABLED={raw}\n")
    s = Settings(_env_file=f)
    assert s.analytics_explain_enabled is False
    assert s.analytics_llm_enabled is True and s.analytics_llm_active is True  # classification and calculation stay on


def test_analytics_explain_enabled_defaults_to_true_and_a_blank_value_means_unset(tmp_path, monkeypatch):
    assert Settings(_env_file=write(tmp_path / "a.env", "LOG_LEVEL=INFO\n")).analytics_explain_enabled is True
    assert Settings(_env_file=write(tmp_path / "b.env", "ANALYTICS_EXPLAIN_ENABLED=\n")).analytics_explain_enabled is True
    monkeypatch.setenv("ANALYTICS_EXPLAIN_ENABLED", "")  # a blank process variable must not crash startup
    assert Settings(_env_file=None).analytics_explain_enabled is True


def test_the_process_environment_overrides_the_file_for_the_explain_switch(tmp_path, monkeypatch):
    f = write(tmp_path / "b.env", "ANALYTICS_EXPLAIN_ENABLED=true\n")
    monkeypatch.setenv("ANALYTICS_EXPLAIN_ENABLED", "false")
    assert Settings(_env_file=f).analytics_explain_enabled is False


def test_the_explain_switch_is_server_side_only():
    """No NEXT_PUBLIC_ variable or frontend file may carry server configuration."""
    repo = BACKEND.parent
    for rel in ("frontend/.env.example", "frontend/next.config.ts"):
        p = repo / rel
        if p.exists():
            text = p.read_text(encoding="utf-8")
            assert "ANALYTICS_EXPLAIN" not in text and "NEXT_PUBLIC_ANALYTICS" not in text
