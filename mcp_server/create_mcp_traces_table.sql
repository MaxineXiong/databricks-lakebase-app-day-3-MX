-- MCP Traces Table for Alpaca Paper Trading MCP Server
-- Stores tracing information for all MCP tool invocations
-- Each trace includes a unique session ID to group calls from the same agent session

CREATE TABLE IF NOT EXISTS mcp_traces (
    trace_id VARCHAR(36) PRIMARY KEY,
    session_id VARCHAR(36) NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    tool_name VARCHAR(100) NOT NULL,
    parameters JSONB,
    result JSONB,
    user_email VARCHAR(255),
    duration_ms NUMERIC(10, 2),
    status VARCHAR(20) NOT NULL,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Index for querying by session
CREATE INDEX IF NOT EXISTS idx_mcp_traces_session_id ON mcp_traces(session_id);

-- Index for querying by user
CREATE INDEX IF NOT EXISTS idx_mcp_traces_user_email ON mcp_traces(user_email);

-- Index for querying by tool name
CREATE INDEX IF NOT EXISTS idx_mcp_traces_tool_name ON mcp_traces(tool_name);

-- Index for querying by timestamp (most recent traces)
CREATE INDEX IF NOT EXISTS idx_mcp_traces_timestamp ON mcp_traces(timestamp DESC);

-- Index for querying by status (find errors)
CREATE INDEX IF NOT EXISTS idx_mcp_traces_status ON mcp_traces(status);

-- Composite index for common query pattern: recent traces for a specific user
CREATE INDEX IF NOT EXISTS idx_mcp_traces_user_timestamp ON mcp_traces(user_email, timestamp DESC);

-- Comments for documentation
COMMENT ON TABLE mcp_traces IS 'Tracing table for MCP tool invocations. Each trace captures input parameters, results, execution time, and session information.';
COMMENT ON COLUMN mcp_traces.trace_id IS 'Unique identifier for this trace (UUID)';
COMMENT ON COLUMN mcp_traces.session_id IS 'Session identifier - groups all tool calls from the same agent session (generated per server instance)';
COMMENT ON COLUMN mcp_traces.timestamp IS 'When the tool was invoked';
COMMENT ON COLUMN mcp_traces.tool_name IS 'Name of the MCP tool that was called';
COMMENT ON COLUMN mcp_traces.parameters IS 'JSON object containing the input parameters';
COMMENT ON COLUMN mcp_traces.result IS 'Standardized JSON result: {"tool_name": str, "success": bool, "message": str, "data": object}';
COMMENT ON COLUMN mcp_traces.user_email IS 'Email of the user who invoked the tool';
COMMENT ON COLUMN mcp_traces.duration_ms IS 'Execution duration in milliseconds';
COMMENT ON COLUMN mcp_traces.status IS 'Execution status: success or error';
COMMENT ON COLUMN mcp_traces.error_message IS 'Error message if status is error';