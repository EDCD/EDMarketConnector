# flake8: noqa
# mypy: ignore-errors
"""Tets the l10n system."""

import pytest
from unittest.mock import patch
import sys
import l10n


@pytest.fixture
def mock_l10n_dir(tmp_path):
    """Creates a mock L10n directory with some sample .strings files."""
    l10n_dir = tmp_path / "L10n"
    l10n_dir.mkdir()

    # Create a dummy Spanish translation file
    es_file = l10n_dir / "es.strings"
    es_file.write_text('"Hello" = "Hola";\n"!Language" = "Español";', encoding="utf-8")

    # Create a dummy German translation file
    de_file = l10n_dir / "de.strings"
    de_file.write_text('"Hello" = "Hallo";', encoding="utf-8")

    return l10n_dir


class TestTranslations:

    def test_regex_parsing(self):
        """Verify that the TRANS_RE regex correctly parses OSX-style string lines."""
        line = ' "Key Name" = "Translated Value" ; '
        match = l10n.Translations.TRANS_RE.match(line)
        assert match is not None
        assert match.group(1) == "Key Name"
        assert match.group(2) == "Translated Value"

    def test_regex_escaped_quotes(self):
        """Verify that escaped quotes in strings are handled by the regex."""
        line = r' "Click \"Here\"" = "Presione \"Aquí\"" ;'
        match = l10n.Translations.TRANS_RE.match(line)
        assert match is not None
        assert match.group(1) == r"Click \"Here\""
        assert match.group(2) == r"Presione \"Aquí\""

    def test_available_languages(self, mock_l10n_dir):
        """Verify available() scans the directory for .strings files."""
        trans = l10n.Translations()
        with patch.object(l10n.Translations, "respath", return_value=mock_l10n_dir):
            langs = trans.available()
            assert "es" in langs
            assert "de" in langs
            assert "en" not in langs  # English is fallback, not usually a file

    def test_contents_loading(self, mock_l10n_dir):
        """Test loading a specific language file into a dictionary."""
        trans = l10n.Translations()
        with patch.object(l10n.Translations, "respath", return_value=mock_l10n_dir):
            data = trans.contents("es")
            assert data["Hello"] == "Hola"
            assert data["!Language"] == "Español"

    def test_translate_fallback(self):
        """Test that missing translations return the original string."""
        trans = l10n.Translations()
        trans.install_dummy()
        # Should return the key itself if no translation is loaded
        assert trans.translate("Unknown Key") == "Unknown Key"

    def test_install_logic_selection(self, mock_l10n_dir):
        """Test that install() picks the correct language based on preferred languages."""
        trans = l10n.Translations()
        with patch.object(l10n.Translations, "respath", return_value=mock_l10n_dir):
            with patch(
                "l10n.Locale.preferred_languages",
                return_value=["fr-FR", "es-ES", "en-US"],
            ):
                # It should skip 'fr' (missing) and pick 'es' because 'es-ES' base matches 'es'
                trans.install()
                assert trans.translations[None]["Hello"] == "Hola"


class TestLocaleUtils:

    def test_string_from_number_formatting(self):
        """Test locale-aware number to string conversion."""
        val = 1234.56
        # Formatting with 1 decimal place
        res = l10n.Locale.string_from_number(val, decimals=1)

        # Instead of looking for '1234', we verify the digits are present
        # regardless of whether the locale uses '1,234.6', '1.234,6', or '1 234.6'
        digits_only = "".join(filter(str.isdigit, res))

        assert "1234" in digits_only
        # Verify the decimal rounding (56 rounded to 1 decimal is 6)
        assert "6" in digits_only[-1]

    def test_number_from_string(self):
        """Test string to number conversion logic."""
        # Using a value that is likely safe across common locales
        assert l10n.Locale.number_from_string("100") == 100
        assert l10n.Locale.number_from_string("not_a_number") is None

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific logic")
    def test_preferred_languages_mapping(self):
        """Verify the zh-CN to zh-Hans hack works."""
        with patch("sys.platform", "win32"):
            # Mock the Windows specific API return
            with patch("l10n._wszarray_to_list", return_value=["en-US", "zh-CN"]):
                # We mock the DLL call to avoid crashes
                with patch("l10n.GetUserPreferredUILanguages", return_value=True):
                    langs = l10n.Locale.preferred_languages()
                    assert "zh-Hans" in langs
                    assert "zh-CN" not in langs
