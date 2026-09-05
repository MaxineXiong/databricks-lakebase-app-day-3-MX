# MCP Server Tracing

This MCP server includes comprehensive tracing functionality that logs every tool invocation to a Lakebase Postgres table.

## Features

* **Automatic tracing**: All MCP tool calls are automatically traced via the `@trace_tool` decorator
* **Session tracking**: Each server instance generates a unique session ID (UUID) that groups all tool calls from that session
* **Standardized result format**: All tool results follow a consistent structure for easy analysis
* **Detailed capture**: Traces include:
  * Input parameters (JSON)
  * Standardized result (JSON) with tool_name, success, message, and data
  * Execution duration (milliseconds)
  * Success/error status (reflects actual tool execution, not just exceptions)
  * Error messages (if applicable)
  * User email (from X-Forwarded-User header or service principal)
  * Timestamp

## Standardized Result Format

All tool traces use a **standardized result structure** for consistent logging and analysis:

```json
{
  "tool_name": "get_quote",
  "success": true,
  "message": "Successfully executed get_quote",
  "data": {
    "symbol": "AAPL",
    "price": 150.25,
    "as_of": "2025-01-21T10:30:00"
  }
}
```

### Result Fields

* **tool_name**: Name of the tool that was executed
* **success**: Boolean indicating whether the tool execution was successful
  * `true`: Tool executed successfully and returned expected results
  * `false`: Tool encountered an error or returned an error status
* **message**: Human-readable description of what happened
  * Success: "Successfully executed {tool_name}" or custom success message
  * Failure: Error message or reason for failure
* **data**: The actual tool result (may be null for errors)

### Status Detection

The tracing framework intelligently detects the actual execution status:

1. **Exception raised**: `success = false`, message contains exception details
2. **Tool returns `{"status": "error", ...}`**: `success = false`, uses tool's message
3. **Tool returns `{"status": "success", ...}`**: `success = true`, uses tool's message
4. **Tool returns `{"status": "not_found", ...}`**: `success = false` (handled failure)
5. **No exception, no status field**: `success = true` (assumed success)

### Benefits

* **Consistent structure**: Every trace result follows the same format
* **Easy querying**: Extract success/failure info with `result->>'success'`
* **Accurate status**: Status reflects actual tool behavior, not just exception handling
* **Detailed messages**: Human-readable messages for debugging and monitoring
* **Original data preserved**: Full tool result stored in `data` field

## Setup

### 1. Create the traces table

Run the SQL script to create the `mcp_traces` table in your Lakebase database:

```bash
psql -h <lakebase-host> -U <user> -d <database> -f create_mcp_traces_table.sql
```

Or use the Lakebase connection in your notebook:

```python
import lakebase

with open('create_mcp_traces_table.sql', 'r') as f:
    sql = f.read()
    lakebase.run_write(sql)
```

### 2. Tracing is automatic

Once the table exists, tracing happens automatically for every tool call. No additional configuration needed!

## Querying Traces

Use the helper functions in `query_traces.py` to analyze your traces:

```python
import lakebase
from query_traces import *

# Get the 20 most recent traces
recent = get_recent_traces(lakebase, limit=20)

# Get all traces for a specific session
session_traces = get_session_traces(lakebase, session_id='abc-123-def-456')

# Get traces for a specific user
user_traces = get_user_traces(lakebase, email='user@example.com')

# Get tool usage statistics
stats = get_tool_stats(lakebase)

# Get only error traces
errors = get_error_traces(lakebase)

# Get a session summary
summary = get_session_summary(lakebase, session_id='abc-123-def-456')

# Analyze standardized results
result_analysis = get_standardized_result_analysis(lakebase, tool_name='get_quote')

# Get common failure reasons
failures = get_failure_reasons(lakebase, tool_name='execute_trade')

# Calculate success rate based on actual tool results
success_rates = get_success_rate_by_tool(lakebase)

# Find slow operations
slow_ops = get_slow_operations(lakebase, min_duration_ms=2000)
```

## Session IDs

Each MCP server instance generates a unique session ID when it starts:

* **Generated**: On server startup using `uuid.uuid4()`
* **Lifetime**: Persists for the entire server lifetime
* **Reset**: New session ID on server restart
* **Purpose**: Group all tool calls from the same agent session together

### Finding your session ID

The session ID is logged when the server starts and included in every trace log message:

```
INFO:alpaca-mcp-server:Traced get_quote call: trace-id (session: session-id)
```

You can also query for active sessions:

```sql
SELECT DISTINCT session_id, MIN(timestamp) as session_start, MAX(timestamp) as session_end
FROM mcp_traces
GROUP BY session_id
ORDER BY session_start DESC
LIMIT 10;
```

## Table Schema

```sql
CREATE TABLE mcp_traces (
    trace_id VARCHAR(36) PRIMARY KEY,           -- Unique trace ID (UUID)
    session_id VARCHAR(36) NOT NULL,            -- Session ID (groups calls)
    timestamp TIMESTAMP NOT NULL,                -- When the call happened
    tool_name VARCHAR(100) NOT NULL,             -- Which tool was called
    parameters JSONB,                            -- Input parameters
    result JSONB,                                -- Output result
    user_email VARCHAR(255),                     -- User who made the call
    duration_ms NUMERIC(10, 2),                  -- Execution time
    status VARCHAR(20) NOT NULL,                 -- 'success' or 'error'
    error_message TEXT,                          -- Error details if failed
    created_at TIMESTAMP NOT NULL DEFAULT NOW()  -- Record creation time
);
```

## Example Queries

### Most frequently used tools

```sql
SELECT tool_name, COUNT(*) as call_count
FROM mcp_traces
GROUP BY tool_name
ORDER BY call_count DESC;
```

### Slowest tool calls

```sql
SELECT tool_name, trace_id, duration_ms, timestamp
FROM mcp_traces
WHERE status = 'success'
ORDER BY duration_ms DESC
LIMIT 20;
```

### Error rate by tool

```sql
SELECT 
    tool_name,
    COUNT(*) as total_calls,
    SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors,
    (SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END)::float / COUNT(*)::float * 100) as error_rate
FROM mcp_traces
GROUP BY tool_name
ORDER BY error_rate DESC;
```

### Session timeline

```sql
SELECT 
    timestamp,
    tool_name,
    duration_ms,
    status
FROM mcp_traces
WHERE session_id = 'your-session-id'
ORDER BY timestamp ASC;
```

### User activity

```sql
SELECT 
    user_email,
    COUNT(*) as total_calls,
    COUNT(DISTINCT session_id) as sessions,
    MIN(timestamp) as first_call,
    MAX(timestamp) as last_call
FROM mcp_traces
GROUP BY user_email
ORDER BY total_calls DESC;
```

### Query standardized results

```sql
-- Get success rate by analyzing result.success field
SELECT 
    tool_name,
    COUNT(*) as total_calls,
    SUM(CASE WHEN (result->>'success')::boolean = true THEN 1 ELSE 0 END) as successful,
    SUM(CASE WHEN (result->>'success')::boolean = false THEN 1 ELSE 0 END) as failed,
    ROUND(100.0 * SUM(CASE WHEN (result->>'success')::boolean = true THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
FROM mcp_traces
GROUP BY tool_name
ORDER BY total_calls DESC;
```

```sql
-- Get most common failure messages
SELECT 
    tool_name,
    result->>'message' as failure_message,
    COUNT(*) as occurrences,
    MAX(timestamp) as last_seen
FROM mcp_traces
WHERE (result->>'success')::boolean = false
GROUP BY tool_name, result->>'message'
ORDER BY occurrences DESC
LIMIT 20;
```

```sql
-- View detailed trace with parsed result
SELECT 
    trace_id,
    tool_name,
    result->>'success' as result_success,
    result->>'message' as result_message,
    status as trace_status,
    duration_ms,
    timestamp
FROM mcp_traces
ORDER BY timestamp DESC
LIMIT 50;
```

## Performance Considerations

* Tracing is **non-blocking** - if trace logging fails, the tool call still succeeds
* All trace writes are logged but errors are caught and logged
* Indexes on `session_id`, `user_email`, `tool_name`, `timestamp`, and `status` ensure fast queries
* Consider archiving or partitioning the table for very high-volume deployments

## Troubleshooting

### Traces not appearing

1. Check that the `mcp_traces` table exists:
   ```sql
   SELECT * FROM information_schema.tables WHERE table_name = 'mcp_traces';
   ```

2. Check server logs for trace errors:
   ```
   Failed to log trace for <tool_name>
   ```

3. Verify Lakebase connection in `lakebase.py` is working

### Session ID not grouping correctly

The session ID is generated once per server startup. If you restart the server, a new session ID is generated. This is by design - each server instance represents a new "session".

## Privacy & Security

* **PII Warning**: Parameters and results are stored as JSON, which may contain sensitive data
* **User tracking**: User emails are captured for attribution
* **Data retention**: Consider implementing a retention policy to delete old traces
* **Access control**: Restrict access to the `mcp_traces` table appropriately