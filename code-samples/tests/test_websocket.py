"""
Unit Tests for WebSocket Streaming Pattern
==========================================

Demonstrates testing patterns for FastAPI WebSocket applications.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
import json
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi_patterns.websocket_streaming import app, ConnectionManager, manager


class TestConnectionManager:
    """Test suite for WebSocket ConnectionManager."""

    @pytest.fixture
    def connection_manager(self):
        """Provide fresh ConnectionManager instance."""
        return ConnectionManager()

    @pytest.mark.asyncio
    async def test_connect_adds_client(self, connection_manager):
        """Test that connecting adds client to active connections."""
        mock_websocket = AsyncMock()

        await connection_manager.connect(mock_websocket, "client1")

        assert "client1" in connection_manager.active_connections
        assert connection_manager.active_connections["client1"] == mock_websocket
        mock_websocket.accept.assert_called_once()

    def test_disconnect_removes_client(self, connection_manager):
        """Test that disconnecting removes client."""
        mock_websocket = Mock()
        connection_manager.active_connections["client1"] = mock_websocket

        connection_manager.disconnect("client1")

        assert "client1" not in connection_manager.active_connections

    @pytest.mark.asyncio
    async def test_send_message_to_specific_client(self, connection_manager):
        """Test sending message to specific client."""
        mock_websocket = AsyncMock()
        connection_manager.active_connections["client1"] = mock_websocket

        message = {"type": "test", "content": "Hello"}
        await connection_manager.send_message("client1", message)

        mock_websocket.send_json.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_broadcast_to_all_clients(self, connection_manager):
        """Test broadcasting message to all connected clients."""
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        connection_manager.active_connections = {
            "client1": mock_ws1,
            "client2": mock_ws2
        }

        message = {"type": "broadcast", "content": "Everyone"}
        await connection_manager.broadcast(message)

        mock_ws1.send_json.assert_called_once_with(message)
        mock_ws2.send_json.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_broadcast_handles_disconnected_clients(self, connection_manager):
        """Test that broadcast removes clients that fail."""
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        mock_ws2.send_json.side_effect = Exception("Connection lost")

        connection_manager.active_connections = {
            "client1": mock_ws1,
            "client2": mock_ws2
        }

        message = {"type": "test"}
        await connection_manager.broadcast(message)

        # Client2 should be removed after error
        assert "client2" not in connection_manager.active_connections
        assert "client1" in connection_manager.active_connections


class TestWebSocketEndpoints:
    """Test suite for WebSocket endpoints."""

    @pytest.fixture
    def client(self):
        """Provide FastAPI TestClient."""
        return TestClient(app)

    def test_health_check_endpoint(self, client):
        """Test /health endpoint returns correct status."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "active_connections" in data
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_websocket_connection_lifecycle(self, client):
        """Test WebSocket connection and disconnection."""
        with patch('fastapi_patterns.websocket_streaming.stream_agent_response') as mock_stream:
            mock_stream.return_value = None

            with client.websocket_connect("/ws/agent/test_client") as websocket:
                # Connection should be established
                assert "test_client" in manager.active_connections

            # After context exit, client should be disconnected
            assert "test_client" not in manager.active_connections

    @pytest.mark.asyncio
    async def test_websocket_message_handling(self, client):
        """Test WebSocket handles user messages."""
        with patch('fastapi_patterns.websocket_streaming.stream_agent_response') as mock_stream:
            mock_stream.return_value = None

            with client.websocket_connect("/ws/agent/test_client") as websocket:
                # Send message
                websocket.send_json({
                    "type": "message",
                    "content": "Hello agent",
                    "context": {"user_id": "123"}
                })

                # stream_agent_response should be called
                mock_stream.assert_called_once()

    @pytest.mark.asyncio
    async def test_websocket_ping_pong(self, client):
        """Test WebSocket responds to ping with pong."""
        with client.websocket_connect("/ws/agent/test_client") as websocket:
            # Send ping
            websocket.send_json({"type": "ping"})

            # Should receive pong
            response = websocket.receive_json()
            assert response["type"] == "pong"


class TestStreamingLogic:
    """Test suite for agent response streaming."""

    @pytest.mark.asyncio
    async def test_stream_start_message(self):
        """Test that streaming starts with start indicator."""
        from fastapi_patterns.websocket_streaming import stream_agent_response

        mock_websocket = AsyncMock()

        with patch('fastapi_patterns.websocket_streaming.client.messages.stream') as mock_stream:
            # Mock the stream context manager
            mock_stream_instance = Mock()
            mock_stream_instance.__enter__ = Mock(return_value=mock_stream_instance)
            mock_stream_instance.__exit__ = Mock(return_value=None)
            mock_stream_instance.text_stream = []
            mock_stream_instance.get_final_message.return_value = Mock(
                usage=Mock(input_tokens=10, output_tokens=20)
            )
            mock_stream.return_value = mock_stream_instance

            await stream_agent_response(
                mock_websocket,
                "client1",
                "Test message"
            )

            # Check that start message was sent
            calls = mock_websocket.send_json.call_args_list
            assert any("message_start" in str(call) for call in calls)

    @pytest.mark.asyncio
    async def test_stream_completion_message(self):
        """Test that streaming ends with completion message."""
        from fastapi_patterns.websocket_streaming import stream_agent_response

        mock_websocket = AsyncMock()

        with patch('fastapi_patterns.websocket_streaming.client.messages.stream') as mock_stream:
            mock_stream_instance = Mock()
            mock_stream_instance.__enter__ = Mock(return_value=mock_stream_instance)
            mock_stream_instance.__exit__ = Mock(return_value=None)
            mock_stream_instance.text_stream = ["Hello", " world"]
            mock_stream_instance.get_final_message.return_value = Mock(
                usage=Mock(input_tokens=10, output_tokens=20)
            )
            mock_stream.return_value = mock_stream_instance

            await stream_agent_response(
                mock_websocket,
                "client1",
                "Test"
            )

            # Check that completion message was sent
            calls = mock_websocket.send_json.call_args_list
            assert any("message_complete" in str(call) for call in calls)

    @pytest.mark.asyncio
    async def test_stream_error_handling(self):
        """Test that streaming errors are caught and sent to client."""
        from fastapi_patterns.websocket_streaming import stream_agent_response

        mock_websocket = AsyncMock()

        with patch('fastapi_patterns.websocket_streaming.client.messages.stream') as mock_stream:
            mock_stream.side_effect = Exception("API Error")

            await stream_agent_response(
                mock_websocket,
                "client1",
                "Test"
            )

            # Check that error message was sent
            calls = mock_websocket.send_json.call_args_list
            error_calls = [call for call in calls if "error" in str(call)]
            assert len(error_calls) > 0

    @pytest.mark.asyncio
    async def test_stream_with_context(self):
        """Test streaming with context data."""
        from fastapi_patterns.websocket_streaming import stream_agent_response

        mock_websocket = AsyncMock()
        context = {
            "user_id": "123",
            "preferences": {"theme": "dark"}
        }

        with patch('fastapi_patterns.websocket_streaming.client.messages.stream') as mock_stream:
            mock_stream_instance = Mock()
            mock_stream_instance.__enter__ = Mock(return_value=mock_stream_instance)
            mock_stream_instance.__exit__ = Mock(return_value=None)
            mock_stream_instance.text_stream = []
            mock_stream_instance.get_final_message.return_value = Mock(
                usage=Mock(input_tokens=10, output_tokens=20)
            )
            mock_stream.return_value = mock_stream_instance

            await stream_agent_response(
                mock_websocket,
                "client1",
                "Test message",
                context=context
            )

            # Verify stream was called with context in system prompt
            mock_stream.assert_called_once()
            call_kwargs = mock_stream.call_args[1]
            assert "Context:" in call_kwargs["system"]


class TestProduction:
    """Test production-ready features."""

    def test_cors_middleware_configured(self):
        """Test that CORS middleware is properly configured."""
        # Check that CORS middleware is in app middleware stack
        middleware_types = [type(m) for m in app.user_middleware]
        from fastapi.middleware.cors import CORSMiddleware
        assert CORSMiddleware in [m.cls for m in app.user_middleware]

    def test_health_check_includes_connection_count(self, client):
        """Test health check reports active connections."""
        response = client.get("/health")
        data = response.json()

        assert "active_connections" in data
        assert isinstance(data["active_connections"], int)

    @pytest.mark.asyncio
    async def test_connection_cleanup_on_error(self):
        """Test that connections are cleaned up on errors."""
        initial_count = len(manager.active_connections)

        mock_websocket = AsyncMock()
        mock_websocket.receive_text.side_effect = Exception("Connection error")

        await manager.connect(mock_websocket, "error_client")

        # Simulate error and cleanup
        manager.disconnect("error_client")

        assert len(manager.active_connections) == initial_count


# Pytest configuration
@pytest.fixture(autouse=True)
def reset_manager():
    """Reset connection manager before each test."""
    manager.active_connections.clear()
    yield
    manager.active_connections.clear()


# Run with: pytest test_websocket.py -v --asyncio-mode=auto
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
