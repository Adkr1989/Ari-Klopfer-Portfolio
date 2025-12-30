"""
Unit Tests for Multi-Agent Orchestration Pattern
=================================================

Demonstrates testing patterns for agent systems.
Production systems should have comprehensive test coverage.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from claude_agent_sdk.multi_agent_orchestration import SubAgent, AgentOrchestrator


class TestSubAgent:
    """Test suite for SubAgent class."""

    def test_subagent_initialization(self):
        """Test that SubAgent initializes with correct attributes."""
        tools = [{"name": "test_tool", "description": "A test tool"}]
        agent = SubAgent(
            name="test_agent",
            role="Test agent role",
            tools=tools,
            system_prompt="Custom prompt"
        )

        assert agent.name == "test_agent"
        assert agent.role == "Test agent role"
        assert agent.tools == tools
        assert agent.system_prompt == "Custom prompt"

    def test_subagent_default_system_prompt(self):
        """Test that SubAgent generates default system prompt from role."""
        agent = SubAgent(
            name="researcher",
            role="grant researcher",
            tools=[]
        )

        assert agent.system_prompt == "You are a grant researcher."

    @patch('claude_agent_sdk.multi_agent_orchestration.Anthropic')
    def test_execute_success(self, mock_anthropic):
        """Test successful task execution."""
        # Mock Claude API response
        mock_response = Mock()
        mock_response.content = [{"type": "text", "text": "Task completed"}]
        mock_response.usage = Mock(input_tokens=100, output_tokens=50)

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        agent = SubAgent(
            name="test_agent",
            role="test role",
            tools=[]
        )

        result = agent.execute("Test task")

        assert result["success"] is True
        assert result["agent"] == "test_agent"
        assert "usage" in result

    @patch('claude_agent_sdk.multi_agent_orchestration.Anthropic')
    def test_execute_with_context(self, mock_anthropic):
        """Test execution with context data."""
        mock_response = Mock()
        mock_response.content = [{"type": "text", "text": "Done"}]
        mock_response.usage = Mock(input_tokens=100, output_tokens=50)

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        agent = SubAgent(name="agent", role="role", tools=[])

        context = {"user_id": "123", "preferences": {"theme": "dark"}}
        result = agent.execute("Task", context=context)

        assert result["success"] is True

    @patch('claude_agent_sdk.multi_agent_orchestration.Anthropic')
    def test_execute_error_handling(self, mock_anthropic):
        """Test that errors are caught and returned properly."""
        mock_client = Mock()
        mock_client.messages.create.side_effect = Exception("API Error")
        mock_anthropic.return_value = mock_client

        agent = SubAgent(name="agent", role="role", tools=[])

        result = agent.execute("Task")

        assert result["success"] is False
        assert result["agent"] == "agent"
        assert "API Error" in result["error"]


class TestAgentOrchestrator:
    """Test suite for AgentOrchestrator class."""

    def test_orchestrator_initialization(self):
        """Test orchestrator initializes with subagents."""
        agent1 = SubAgent("agent1", "role1", [])
        agent2 = SubAgent("agent2", "role2", [])

        orchestrator = AgentOrchestrator([agent1, agent2])

        assert len(orchestrator.subagents) == 2
        assert "agent1" in orchestrator.subagents
        assert "agent2" in orchestrator.subagents

    @patch('claude_agent_sdk.multi_agent_orchestration.Anthropic')
    def test_route_task(self, mock_anthropic):
        """Test task routing to correct agent."""
        # Mock routing response
        mock_response = Mock()
        mock_response.content = [Mock(text="grant_researcher")]

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        agent1 = SubAgent("grant_researcher", "Research grants", [])
        agent2 = SubAgent("compliance_checker", "Check compliance", [])

        orchestrator = AgentOrchestrator([agent1, agent2])

        agent_name = orchestrator.route_task("Find grants for EV charging")

        assert agent_name == "grant_researcher"

    @patch('claude_agent_sdk.multi_agent_orchestration.Anthropic')
    def test_route_task_fallback(self, mock_anthropic):
        """Test that invalid routing falls back to first agent."""
        # Mock routing response with invalid agent name
        mock_response = Mock()
        mock_response.content = [Mock(text="nonexistent_agent")]

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.return_value = mock_client

        agent1 = SubAgent("agent1", "role1", [])
        agent2 = SubAgent("agent2", "role2", [])

        orchestrator = AgentOrchestrator([agent1, agent2])

        agent_name = orchestrator.route_task("Some task")

        # Should fall back to first agent
        assert agent_name == "agent1"

    @patch('claude_agent_sdk.multi_agent_orchestration.SubAgent.execute')
    @patch('claude_agent_sdk.multi_agent_orchestration.Anthropic')
    def test_execute_with_preferred_agent(self, mock_anthropic, mock_execute):
        """Test execution with preferred agent bypasses routing."""
        mock_execute.return_value = {
            "success": True,
            "agent": "agent2",
            "result": "Done"
        }

        agent1 = SubAgent("agent1", "role1", [])
        agent2 = SubAgent("agent2", "role2", [])

        orchestrator = AgentOrchestrator([agent1, agent2])

        result = orchestrator.execute(
            "Task",
            preferred_agent="agent2"
        )

        assert result["agent"] == "agent2"
        # Routing should not have been called
        mock_anthropic.return_value.messages.create.assert_not_called()

    @patch('claude_agent_sdk.multi_agent_orchestration.SubAgent.execute')
    @patch('claude_agent_sdk.multi_agent_orchestration.Anthropic')
    def test_execute_pipeline(self, mock_anthropic, mock_execute):
        """Test pipeline execution with context passing."""
        # Mock successful executions
        mock_execute.side_effect = [
            {"success": True, "agent": "agent1", "result": "Step 1 done"},
            {"success": True, "agent": "agent2", "result": "Step 2 done"},
        ]

        agent1 = SubAgent("agent1", "role1", [])
        agent2 = SubAgent("agent2", "role2", [])

        orchestrator = AgentOrchestrator([agent1, agent2])

        tasks = [
            {"description": "First task", "agent": "agent1"},
            {"description": "Second task", "agent": "agent2"},
        ]

        results = orchestrator.execute_pipeline(tasks)

        assert len(results) == 2
        assert results[0]["agent"] == "agent1"
        assert results[1]["agent"] == "agent2"

    def test_execution_history_tracking(self):
        """Test that execution history is tracked."""
        agent = SubAgent("agent", "role", [])
        orchestrator = AgentOrchestrator([agent])

        # Mock execute to avoid API calls
        with patch.object(SubAgent, 'execute') as mock_execute:
            mock_execute.return_value = {
                "success": True,
                "agent": "agent",
                "result": "Done"
            }

            orchestrator.execute("Task 1")
            orchestrator.execute("Task 2")

        assert len(orchestrator.execution_history) == 2
        assert orchestrator.execution_history[0]["task"] == "Task 1"
        assert orchestrator.execution_history[1]["task"] == "Task 2"


class TestIntegration:
    """Integration tests for complete workflows."""

    @patch('claude_agent_sdk.multi_agent_orchestration.Anthropic')
    def test_full_grant_research_workflow(self, mock_anthropic):
        """Test complete grant research workflow."""
        # Mock all API responses
        mock_client = Mock()

        # Routing response
        routing_response = Mock()
        routing_response.content = [Mock(text="grant_researcher")]

        # Task execution response
        task_response = Mock()
        task_response.content = [{"type": "text", "text": "Found 5 grants"}]
        task_response.usage = Mock(input_tokens=100, output_tokens=50)

        mock_client.messages.create.side_effect = [
            routing_response,
            task_response
        ]
        mock_anthropic.return_value = mock_client

        # Create agents
        researcher = SubAgent(
            "grant_researcher",
            "Search for grants",
            [{"name": "search_grants"}]
        )

        orchestrator = AgentOrchestrator([researcher])

        # Execute task
        result = orchestrator.execute(
            "Find renewable energy grants in Illinois"
        )

        assert result["success"] is True
        assert result["agent"] == "grant_researcher"


# Pytest fixtures
@pytest.fixture
def sample_tools():
    """Provide sample tool definitions for testing."""
    return [
        {
            "name": "search_database",
            "description": "Search a database",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"]
            }
        }
    ]


@pytest.fixture
def mock_claude_client():
    """Provide mocked Claude API client."""
    with patch('claude_agent_sdk.multi_agent_orchestration.Anthropic') as mock:
        client = Mock()
        mock.return_value = client
        yield client


# Run tests with: pytest test_orchestration.py -v
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
