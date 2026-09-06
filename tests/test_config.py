from buhgalya.config import Settings


def test_empty_workspace_id_is_allowed_before_bootstrap() -> None:
    settings = Settings(default_workspace_id="")

    assert settings.default_workspace_id is None
