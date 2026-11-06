import pytest


@pytest.fixture(autouse=True)
def auto_enable(enable_custom_integrations, mock_bluetooth):
    """Load custom_components/ and stub out Bluetooth hardware."""
