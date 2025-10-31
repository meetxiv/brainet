"""
Test cases for the context analyzer.
"""

import unittest
from datetime import datetime, timedelta
from pathlib import Path

from brainet.core.models import WorkflowInsight, SessionInfo, ActiveFileInfo
from brainet.core.context_analyzer import ContextAnalyzer

class TestContextAnalyzer(unittest.TestCase):
    """Test cases for context analysis functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = Path("/tmp/brainet_test")
        self.analyzer = ContextAnalyzer(self.test_dir)

    def test_add_insight(self):
        """Test adding workflow insights."""
        now = datetime.now()
        insight = WorkflowInsight(
            type="deep_focus",
            description="Test insight",
            confidence=0.8,
            timestamp=now
        )

        self.analyzer.add_insight(insight)
        recent = self.analyzer.get_current_insights(1)
        
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0].type, "deep_focus")
        self.assertEqual(recent[0].description, "Test insight")

    def test_analyze_session(self):
        """Test session analysis."""
        now = datetime.now()
        files = [
            self.test_dir / "test1.py",
            self.test_dir / "test2.py"
        ]

        session = self.analyzer.analyze_session(
            files,
            now - timedelta(hours=1),
            now
        )

        self.assertEqual(len(session.active_files), 2)
        self.assertEqual(session.total_edits, 20)  # 10 per file from placeholder
        self.assertIsInstance(session, SessionInfo)

    def test_analyze_workflow(self):
        """Test workflow analysis across sessions."""
        now = datetime.now()
        
        # Session 1: Single file focus
        session1 = SessionInfo(
            start_time=now - timedelta(hours=2),
            end_time=now - timedelta(hours=1),
            active_files=[
                ActiveFileInfo(
                    path=self.test_dir / "focus.py",
                    time_spent=timedelta(hours=1),
                    edit_count=25,
                    last_accessed=now - timedelta(hours=1)
                )
            ],
            total_edits=25,
            workflow_insights=[]
        )

        # Session 2: Task switch
        session2 = SessionInfo(
            start_time=now - timedelta(hours=1),
            end_time=now,
            active_files=[
                ActiveFileInfo(
                    path=self.test_dir / "different.py",
                    time_spent=timedelta(hours=1),
                    edit_count=15,
                    last_accessed=now
                )
            ],
            total_edits=15,
            workflow_insights=[]
        )

        insights = self.analyzer.analyze_workflow([session1, session2])
        
        self.assertTrue(any(i.type == "deep_focus" for i in insights))
        self.assertTrue(any(i.type == "task_switch" for i in insights))

    def test_get_current_insights(self):
        """Test retrieving recent insights."""
        now = datetime.now()
        insights = [
            WorkflowInsight(
                type=f"test_{i}",
                description=f"Test {i}",
                confidence=0.8,
                timestamp=now - timedelta(minutes=i)
            )
            for i in range(10)
        ]

        for insight in insights:
            self.analyzer.add_insight(insight)

        recent = self.analyzer.get_current_insights(5)
        
        self.assertEqual(len(recent), 5)
        # Should be in reverse chronological order
        self.assertEqual(recent[0].type, "test_0")
        self.assertEqual(recent[-1].type, "test_4")

if __name__ == '__main__':
    unittest.main()