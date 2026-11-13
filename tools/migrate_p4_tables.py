"""
GARI Phase P4 Database Migration
Creates tables for:
- Agent Executions & Task Queue
- Tool Invocation Logs & Observability
- Human-in-the-loop Approval Requests
"""

import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gari_p4_migration")

DB_PATH = "database/disease_detector.db"

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Agent Executions Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            execution_id TEXT UNIQUE NOT NULL,
            agent_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            organization_id INTEGER,
            task_type TEXT NOT NULL,
            input_context TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending', -- pending, running, completed, failed, cancelled, requires_human_review
            output_payload TEXT,
            tool_invocations TEXT, -- JSON array of tool calls
            latency_ms REAL,
            requires_approval INTEGER DEFAULT 0,
            error_message TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed_at DATETIME,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_agent_exec_user ON agent_executions(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_agent_exec_agent ON agent_executions(agent_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_agent_exec_status ON agent_executions(status)")

    # 2. Human-In-The-Loop Approval Requests Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_approval_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            approval_id TEXT UNIQUE NOT NULL,
            execution_id TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            organization_id INTEGER,
            action_type TEXT NOT NULL, -- e.g. 'assign_task', 'send_message', 'modify_role', 'delete_record'
            action_summary TEXT NOT NULL,
            proposed_payload TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending', -- pending, approved, rejected, expired
            reviewed_by_user_id INTEGER,
            review_notes TEXT,
            reviewed_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (execution_id) REFERENCES agent_executions(execution_id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_agent_appr_status ON agent_approval_requests(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_agent_appr_user ON agent_approval_requests(user_id)")

    conn.commit()
    conn.close()
    logger.info("P4 migration completed successfully!")

if __name__ == '__main__':
    migrate()

