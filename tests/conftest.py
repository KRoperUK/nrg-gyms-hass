"""Global fixtures for NRG Gyms integration."""
import pytest
import pytest_socket

# Enable homeassistant plugin
pytest_plugins = "pytest_homeassistant_custom_component"

# This fixture enables loading custom integrations from all subdirectories.
@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield

# Override socket_enabled fixture to handle live tests correctly
@pytest.fixture(autouse=True)
def socket_enabled(pytestconfig, request):
    """Enable sockets for live tests, disable for others."""
    import pytest_socket
    
    # Check for live marker
    if request.node.get_closest_marker("live"):
        import socket
        import _socket
        socket.socket = _socket.socket
    else:
        pytest_socket.disable_socket(allow_unix_socket=True)
    yield
    # Ensure disabled after test
    pytest_socket.disable_socket(allow_unix_socket=True)
