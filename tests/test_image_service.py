"""
Tests for image_service.py and nakshatra_archetypes re-exports.
"""

from unittest.mock import patch, MagicMock
import pytest
from image_service import generate_nakshatra_portrait, get_openai_api_key
from nakshatra_archetypes import (
    generate_nakshatra_portrait as reexported_portrait_func,
    get_nakshatra_archetype,
)


def test_nakshatra_archetype_lookup():
    """Verify Nakshatra deity and blessing metadata returns properly."""
    res = get_nakshatra_archetype("Ashwini")
    assert "Ashwini Kumaras" in res["title"]
    assert "deity" in res
    assert "blessing_message" in res
    assert "posture" in res
    assert "setting" in res


def test_reexported_forwarder_call():
    """Verify nakshatra_archetypes forwards calls to image_service.generate_nakshatra_portrait."""
    with patch("image_service.get_openai_api_key", return_value=None):
        res = reexported_portrait_func("fake_b64", "Ashwini")
        assert res["status"] == "missing_api_key"



def test_missing_api_key(monkeypatch):
    """Ensure graceful handling when OPENAI_API_KEY is not configured."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with patch("image_service.get_openai_api_key", return_value=None):
        result = generate_nakshatra_portrait("fake_base64", "Ashwini")
        assert result["status"] == "missing_api_key"
        assert result["image_url"] is None
        assert "Ashwini Kumaras" in result["archetype_title"]


def test_missing_photo(monkeypatch):
    """Ensure graceful handling when photo_base64 is empty."""
    with patch("image_service.get_openai_api_key", return_value="fake_test_key"):
        result = generate_nakshatra_portrait("", "Ashwini")
        assert result["status"] == "no_photo"
        assert result["image_url"] is None


def test_successful_mocked_image_generation():
    """Verify portrait generation flow with mocked OpenAI client."""
    # 1x1 transparent PNG base64
    sample_b64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_item = MagicMock()
    mock_item.url = "https://images.openai.com/mock-portrait.jpg"
    mock_resp.data = [mock_item]
    mock_client.images.generate.return_value = mock_resp

    with patch("image_service.get_openai_api_key", return_value="fake_key"), \
         patch("image_service.OpenAI", return_value=mock_client):
        result = generate_nakshatra_portrait(sample_b64, "Rohini", guest_name="Ananya")
        assert result["status"] == "success"
        assert result["image_url"] == "https://images.openai.com/mock-portrait.jpg"
        assert "Lord Krishna" in result["archetype_title"]
        mock_client.images.generate.assert_called()


def test_generate_divine_blessing_card():
    """Verify generate_divine_blessing_card produces correct deity and simple blessing."""
    from image_service import generate_divine_blessing_card
    with patch("image_service.get_openai_api_key", return_value=None):
        card = generate_divine_blessing_card(atmakaraka="Jupiter", nakshatra_name="Swati", seeker_name="Aarav")
        assert card["status"] == "missing_api_key"
        assert card["deity"] == "Goddess Saraswati"
        assert "Goddess Saraswati is your Nakshatra" in card["blessing_message"]
        assert "guide you on your life journey" in card["blessing_message"]

