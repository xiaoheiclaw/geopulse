"""Tests for mental models loading."""
from pathlib import Path
from geopulse.mental_models import load_models, build_prompt_injection


class TestLoadModels:
    def test_loads_all_models(self):
        models = load_models()
        assert len(models) == 8

    def test_model_has_required_fields(self):
        models = load_models()
        for name, model in models.items():
            assert "title" in model
            assert "prompt_template" in model
            assert len(model["prompt_template"]) > 0


class TestBuildPromptInjection:
    def test_returns_string(self):
        result = build_prompt_injection()
        assert isinstance(result, str)
        assert len(result) > 100

    def test_contains_all_model_names(self):
        result = build_prompt_injection()
        assert "威慑理论" in result
        assert "反事实" in result
        assert "边缘策略" in result
