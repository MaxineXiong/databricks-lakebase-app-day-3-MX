"""
Helper functions to query MCP traces from Lakebase.

Usage:
    import lakebase
    from query_traces import *
    
    # Get recent traces
    traces = get_recent_traces(lakebase, limit=20)
    
    # Get traces for a specific session
    session_traces = get_session_traces(lakebase, session_id='abc-123')
    
    # Get traces for a specific user
    user_traces = get_user_traces(lakebase, email='user@example.com')
"""

def get_recent_traces(lakebase, limit=50):
    """
    Get the most recent MCP traces.
    
    Args:
        lakebase: Lakebase connection object
        limit: Maximum number of traces to return
    
    Returns:
        List of trace dicts
    """
    sql = """
    SELECT 
        trace_id,
        session_id,
        timestamp,
        tool_name,
        parameters,
        result,
        user_email,
        duration_ms,
        status,
        error_message
    FROM mcp_traces
    ORDER BY timestamp DESC
    LIMIT %s
    """
    return lakebase.run_query(sql, (limit,))


def get_session_traces(lakebase, session_id, limit=100):
    """
    Get all traces for a specific session ID.
    
    Args:
        lakebase: Lakebase connection object
        session_id: The session ID to filter by
        limit: Maximum number of traces to return
    
    Returns:
        List of trace dicts ordered by timestamp
    """
    sql = """
    SELECT 
        trace_id,
        session_id,
        timestamp,
        tool_name,
        parameters,
        result,
        user_email,
        duration_ms,
        status,
        error_message
    FROM mcp_traces
    WHERE session_id = %s
    ORDER BY timestamp ASC
    LIMIT %s
    """
    return lakebase.run_query(sql, (session_id, limit))


def get_user_traces(lakebase, email, limit=50):
    """
    Get traces for a specific user.
    
    Args:
        lakebase: Lakebase connection object
        email: User email to filter by
        limit: Maximum number of traces to return
    
    Returns:
        List of trace dicts ordered by timestamp descending
    """
    sql = """
    SELECT 
        trace_id,
        session_id,
        timestamp,
        tool_name,
        parameters,
        result,
        user_email,
        duration_ms,
        status,
        error_message
    FROM mcp_traces
    WHERE user_email = %s
    ORDER BY timestamp DESC
    LIMIT %s
    """
    return lakebase.run_query(sql, (email, limit))


def get_tool_stats(lakebase, tool_name=None):
    """
    Get statistics for tool usage.
    
    Args:
        lakebase: Lakebase connection object
        tool_name: Optional tool name to filter by (None for all tools)
    
    Returns:
        Statistics dict with call counts, avg duration, success rate
    """
    if tool_name:
        sql = """
        SELECT 
            tool_name,
            COUNT(*) as total_calls,
            AVG(duration_ms) as avg_duration_ms,
            SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
            SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as error_count,
            (SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END)::float / COUNT(*)::float * 100) as success_rate
        FROM mcp_traces
        WHERE tool_name = %s
        GROUP BY tool_name
        """
        return lakebase.run_query(sql, (tool_name,))
    else:
        sql = """
        SELECT 
            tool_name,
            COUNT(*) as total_calls,
            AVG(duration_ms) as avg_duration_ms,
            SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
            SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as error_count,
            (SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END)::float / COUNT(*)::float * 100) as success_rate
        FROM mcp_traces
        GROUP BY tool_name
        ORDER BY total_calls DESC
        """
        return lakebase.run_query(sql)


def get_error_traces(lakebase, limit=50):
    """
    Get traces that resulted in errors.
    
    Args:
        lakebase: Lakebase connection object
        limit: Maximum number of traces to return
    
    Returns:
        List of error trace dicts
    """
    sql = """
    SELECT 
        trace_id,
        session_id,
        timestamp,
        tool_name,
        parameters,
        user_email,
        duration_ms,
        error_message
    FROM mcp_traces
    WHERE status = 'error'
    ORDER BY timestamp DESC
    LIMIT %s
    """
    return lakebase.run_query(sql, (limit,))


def get_session_summary(lakebase, session_id):
    """
    Get a summary of a session's activity.
    
    Args:
        lakebase: Lakebase connection object
        session_id: The session ID to summarize
    
    Returns:
        Summary dict with total calls, unique tools, duration, etc.
    """
    sql = """
    SELECT 
        session_id,
        COUNT(*) as total_calls,
        COUNT(DISTINCT tool_name) as unique_tools,
        MIN(timestamp) as session_start,
        MAX(timestamp) as session_end,
        SUM(duration_ms) as total_duration_ms,
        AVG(duration_ms) as avg_duration_ms,
        SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
        SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as error_count,
        STRING_AGG(DISTINCT user_email, ', ') as users
    FROM mcp_traces
    WHERE session_id = %s
    GROUP BY session_id
    """
    results = lakebase.run_query(sql, (session_id,))
    return results[0] if results else None


def get_standardized_result_analysis(lakebase, tool_name=None):
    """
    Analyze the standardized result format to see success/failure breakdown.
    
    The result column stores: {"tool_name": str, "success": bool, "message": str, "data": any}
    
    Args:
        lakebase: Lakebase connection object
        tool_name: Optional tool name to filter by
    
    Returns:
        List of dicts with tool_name, success status from result.success,
        message, and count
    """
    if tool_name:
        sql = """
        SELECT 
            tool_name,
            result->>'success' as result_success,
            result->>'message' as result_message,
            status as trace_status,
            COUNT(*) as count
        FROM mcp_traces
        WHERE tool_name = %s
        GROUP BY tool_name, result->>'success', result->>'message', status
        ORDER BY count DESC
        """
        return lakebase.run_query(sql, (tool_name,))
    else:
        sql = """
        SELECT 
            tool_name,
            result->>'success' as result_success,
            result->>'message' as result_message,
            status as trace_status,
            COUNT(*) as count
        FROM mcp_traces
        GROUP BY tool_name, result->>'success', result->>'message', status
        ORDER BY tool_name, count DESC
        """
        return lakebase.run_query(sql)


def get_tool_result_messages(lakebase, tool_name, limit=20):
    """
    Get the most common result messages for a specific tool.
    
    Args:
        lakebase: Lakebase connection object
        tool_name: The tool name to analyze
        limit: Maximum number of distinct messages to return
    
    Returns:
        List of dicts with message, success status, count, most recent occurrence
    """
    sql = """
    SELECT 
        result->>'message' as message,
        result->>'success' as success,
        COUNT(*) as count,
        MAX(timestamp) as last_seen
    FROM mcp_traces
    WHERE tool_name = %s
    GROUP BY result->>'message', result->>'success'
    ORDER BY count DESC
    LIMIT %s
    """
    return lakebase.run_query(sql, (tool_name, limit))


def get_trace_detail(lakebase, trace_id):
    """
    Get full details for a specific trace including the standardized result.
    
    Args:
        lakebase: Lakebase connection object
        trace_id: The trace UUID to retrieve
    
    Returns:
        Dict with all trace fields including parsed result structure
    """
    sql = """
    SELECT 
        trace_id,
        session_id,
        timestamp,
        tool_name,
        parameters,
        result,
        result->>'tool_name' as result_tool_name,
        result->>'success' as result_success,
        result->>'message' as result_message,
        user_email,
        duration_ms,
        status,
        error_message
    FROM mcp_traces
    WHERE trace_id = %s
    """
    results = lakebase.run_query(sql, (trace_id,))
    return results[0] if results else None


def get_slow_operations(lakebase, min_duration_ms=1000, limit=50):
    """
    Get traces for operations that took longer than a threshold.
    
    Args:
        lakebase: Lakebase connection object
        min_duration_ms: Minimum duration in milliseconds (default 1000ms = 1s)
        limit: Maximum number of traces to return
    
    Returns:
        List of slow operation traces, ordered by duration descending
    """
    sql = """
    SELECT 
        trace_id,
        session_id,
        timestamp,
        tool_name,
        parameters,
        result->>'message' as result_message,
        result->>'success' as result_success,
        user_email,
        duration_ms,
        status
    FROM mcp_traces
    WHERE duration_ms >= %s
    ORDER BY duration_ms DESC
    LIMIT %s
    """
    return lakebase.run_query(sql, (min_duration_ms, limit))


def get_success_rate_by_tool(lakebase):
    """
    Calculate success rate for each tool based on the standardized result.success field.
    
    This looks at the actual tool result success field, not just the trace status.
    
    Args:
        lakebase: Lakebase connection object
    
    Returns:
        List of dicts with tool_name, total_calls, successful_calls (result.success=true),
        failed_calls, and success_rate percentage
    """
    sql = """
    SELECT 
        tool_name,
        COUNT(*) as total_calls,
        SUM(CASE WHEN (result->>'success')::boolean = true THEN 1 ELSE 0 END) as successful_calls,
        SUM(CASE WHEN (result->>'success')::boolean = false THEN 1 ELSE 0 END) as failed_calls,
        ROUND(100.0 * SUM(CASE WHEN (result->>'success')::boolean = true THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate,
        ROUND(AVG(duration_ms), 2) as avg_duration_ms
    FROM mcp_traces
    GROUP BY tool_name
    ORDER BY total_calls DESC
    """
    return lakebase.run_query(sql)


def get_failure_reasons(lakebase, tool_name=None, limit=20):
    """
    Get the most common failure reasons from the standardized result.message field.
    
    Args:
        lakebase: Lakebase connection object
        tool_name: Optional tool name to filter by
        limit: Maximum number of distinct failure reasons to return
    
    Returns:
        List of dicts with tool_name (if not filtered), failure_message, count,
        most_recent_occurrence
    """
    if tool_name:
        sql = """
        SELECT 
            result->>'message' as failure_message,
            COUNT(*) as count,
            MAX(timestamp) as most_recent
        FROM mcp_traces
        WHERE tool_name = %s
          AND (result->>'success')::boolean = false
        GROUP BY result->>'message'
        ORDER BY count DESC
        LIMIT %s
        """
        return lakebase.run_query(sql, (tool_name, limit))
    else:
        sql = """
        SELECT 
            tool_name,
            result->>'message' as failure_message,
            COUNT(*) as count,
            MAX(timestamp) as most_recent
        FROM mcp_traces
        WHERE (result->>'success')::boolean = false
        GROUP BY tool_name, result->>'message'
        ORDER BY count DESC
        LIMIT %s
        """
        return lakebase.run_query(sql, (limit,))