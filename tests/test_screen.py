import io
from types import SimpleNamespace

import ollama
import pytest
from PIL import Image

from jarvis.core.config import get_settings
from jarvis.tools import default_registry, screen


def png(size=(100, 50)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, "blue").save(out, format="PNG")
    return out.getvalue()


def test_screen_tools_are_registered_as_safe():
    for name in ("take_screenshot", "look_at_screen"):
        assert default_registry.get(name).risk == "safe"


def test_screenshot_is_saved_to_the_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "data_dir", tmp_path)
    monkeypatch.setattr(screen, "capture_png", lambda: png())
    result = screen.take_screenshot()
    saved = list((tmp_path / "screenshots").glob("screenshot-*.png"))
    assert len(saved) == 1 and str(saved[0]) in result


def test_screenshot_failure_is_reported_not_raised(monkeypatch):
    def broken():
        raise OSError("no display")

    monkeypatch.setattr(screen, "capture_png", broken)
    assert screen.take_screenshot().startswith("Error")
    assert screen.look_at_screen().startswith("Error")


def test_large_screenshots_are_downscaled_for_the_model():
    small = Image.open(io.BytesIO(screen._downscale(png((3000, 2000)))))
    assert max(small.size) == screen.MAX_SIDE


def test_look_at_screen_sends_the_image_to_the_vision_model(monkeypatch):
    seen = {}

    class FakeClient:
        def chat(self, model, messages):
            seen.update(model=model, message=messages[0])
            return SimpleNamespace(message=SimpleNamespace(content="A browser with an error."))

    monkeypatch.setattr(screen, "capture_png", lambda: png())
    monkeypatch.setattr(screen.ollama, "Client", FakeClient)
    assert screen.look_at_screen("What is the error?") == "A browser with an error."
    assert seen["model"] == get_settings().vision_model
    assert seen["message"]["images"] and "What is the error?" in seen["message"]["content"]


@pytest.mark.parametrize("status, expected", [(404, "ollama pull"), (500, "failed")])
def test_vision_model_errors_become_text(monkeypatch, status, expected):
    class FakeClient:
        def chat(self, model, messages):
            raise ollama.ResponseError("boom", status)

    monkeypatch.setattr(screen, "capture_png", lambda: png())
    monkeypatch.setattr(screen.ollama, "Client", FakeClient)
    assert expected in screen.look_at_screen()
