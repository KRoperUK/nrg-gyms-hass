"""Test the PerfectGymClient."""

from unittest.mock import MagicMock, patch

from custom_components.nrg_gyms.client import PerfectGymClient


def test_client_init() -> None:
    """Test client initialization."""
    client = PerfectGymClient("user@example.com", "password")
    assert client._email == "user@example.com"
    assert client._password == "password"


@patch("custom_components.nrg_gyms.client.requests.Session")
def test_client_login_success(mock_session_cls: MagicMock) -> None:
    """Test client login success."""
    mock_session = mock_session_cls.return_value
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "OK"
    mock_session.post.return_value = mock_response

    client = PerfectGymClient("user@example.com", "password")
    assert client.login() is True
    mock_session.post.assert_called_once()


@patch("custom_components.nrg_gyms.client.requests.Session")
def test_client_login_failure(mock_session_cls: MagicMock) -> None:
    """Test client login failure."""
    mock_session = mock_session_cls.return_value
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"
    mock_session.post.return_value = mock_response

    client = PerfectGymClient("user@example.com", "password")
    assert client.login() is False
    mock_session.post.assert_called_once()
