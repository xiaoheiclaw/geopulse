"""Tests for mental models loading."""
from geopulse.mental_models import load_models, build_prompt_injection


class TestLoadModels:
    def test_loads_all_models(self):
        models = load_models()
        assert len(models) == 13

    def test_model_has_required_fields(self):
        models = load_models()
        for name, model in models.items():
            assert "title" in model
            assert "prompt_template" in model
            assert len(model["prompt_template"]) > 0
            assert "domains" in model
            assert isinstance(model["domains"], list)


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
        assert "反身性" in result
        assert "供应链级联" in result

    def test_filter_by_domain(self):
        military = build_prompt_injection(domains=["军事"])
        assert "威慑理论" in military
        assert "战争迷雾" in military or "雾中决策" in military
        # Universal models always included
        assert "反事实" in military
        # Financial model should NOT be included
        assert "反身性" not in military

    def test_filter_by_financial_domain(self):
        financial = build_prompt_injection(domains=["金融"])
        assert "反身性" in financial
        # Universal included
        assert "反事实" in financial
        # Military-only should NOT be included
        assert "雾中决策" not in financial
