# Test Suite

This folder contains unit tests for the code samples in this portfolio.

## Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-mock

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_orchestration.py -v

# Run with coverage
pip install pytest-cov
pytest tests/ --cov=code-samples --cov-report=html
```

## Test Files

| File | Coverage | Description |
|------|----------|-------------|
| `test_orchestration.py` | Multi-Agent Orchestration | Tests agent routing, execution, pipelines, error handling |
| `test_websocket.py` | WebSocket Streaming | Tests connection management, streaming, error handling |

## Test Philosophy

These tests demonstrate:
- **Unit Testing** - Individual component testing with mocks
- **Integration Testing** - Complete workflow testing
- **Async Testing** - Proper async/await test patterns
- **Error Handling** - Edge cases and failure scenarios
- **Production Patterns** - Real-world testing approaches

## Coverage Goals

Production systems should maintain:
- **80%+ overall coverage**
- **100% on critical paths** (payment, auth, data integrity)
- **All error paths tested**
- **Edge cases covered**

## Test Structure

```python
class TestComponentName:
    """Test suite for specific component."""

    @pytest.fixture
    def setup_data(self):
        """Provide test data."""
        return {...}

    def test_normal_behavior(self):
        """Test expected behavior."""
        # Arrange
        # Act
        # Assert

    def test_error_handling(self):
        """Test error scenarios."""
        # Test edge cases
```

## Mocking Strategy

- **Mock external APIs** - Don't hit real Anthropic API in tests
- **Mock network calls** - Control responses and errors
- **Use fixtures** - Share setup across tests
- **Isolate tests** - Each test independent

## Production Testing Notes

In production systems, I also implement:
- E2E tests (Playwright for web UIs)
- Load testing (Locust for API endpoints)
- Security testing (OWASP checks)
- Performance profiling (cProfile)

These samples show the unit/integration testing foundation.
