#!/usr/bin/env python3
"""
Practical Example: Using the Standardized Logging Framework

This script demonstrates how to query and analyze MCP traces using the
standardized result format.
"""

import lakebase
from query_traces import *
from datetime import datetime, timedelta
import json


def print_section(title):
    """Print a formatted section header."""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)


def demo_basic_queries():
    """Demonstrate basic trace queries."""
    print_section("1. Recent Traces")
    
    traces = get_recent_traces(lakebase, limit=5)
    for trace in traces:
        result = trace['result']
        success_emoji = "✅" if result.get('success') else "❌"
        print(f"{success_emoji} [{trace['timestamp']}] {trace['tool_name']}")
        print(f"   Message: {result.get('message')}")
        print(f"   Duration: {trace['duration_ms']:.2f}ms")
        print()


def demo_success_rates():
    """Show success rates for each tool."""
    print_section("2. Success Rates by Tool")
    
    rates = get_success_rate_by_tool(lakebase)
    print(f"{'Tool Name':<25} {'Total':<10} {'Success':<10} {'Failed':<10} {'Rate':<10}")
    print("-" * 70)
    
    for rate in rates:
        tool = rate['tool_name']
        total = rate['total_calls']
        success = rate['successful_calls']
        failed = rate['failed_calls']
        rate_pct = rate['success_rate']
        
        # Color code the rate
        emoji = "🟢" if rate_pct >= 95 else "🟡" if rate_pct >= 80 else "🔴"
        
        print(f"{tool:<25} {total:<10} {success:<10} {failed:<10} {emoji} {rate_pct}%")


def demo_failure_analysis():
    """Analyze common failure patterns."""
    print_section("3. Common Failure Reasons")
    
    failures = get_failure_reasons(lakebase, limit=10)
    
    if not failures:
        print("🎉 No failures found! Everything is working perfectly.")
        return
    
    for failure in failures:
        print(f"❌ {failure['tool_name']}")
        print(f"   Reason: {failure['failure_message']}")
        print(f"   Occurrences: {failure['count']}")
        print(f"   Last seen: {failure['most_recent']}")
        print()


def demo_performance_analysis():
    """Analyze performance and find slow operations."""
    print_section("4. Performance Analysis")
    
    # Find slow operations (>1 second)
    slow_ops = get_slow_operations(lakebase, min_duration_ms=1000, limit=5)
    
    if not slow_ops:
        print("⚡ No slow operations found. All tools are fast!")
        return
    
    print("Slowest operations (>1s):")
    print()
    
    for op in slow_ops:
        result_success = op.get('result_success') == 'true'
        emoji = "✅" if result_success else "❌"
        print(f"{emoji} {op['tool_name']} - {op['duration_ms']:.2f}ms")
        print(f"   Message: {op.get('result_message')}")
        print(f"   User: {op['user_email']}")
        print(f"   Time: {op['timestamp']}")
        print()


def demo_tool_specific_analysis(tool_name='get_quote'):
    """Deep dive into a specific tool."""
    print_section(f"5. Detailed Analysis: {tool_name}")
    
    # Get result message breakdown
    messages = get_tool_result_messages(lakebase, tool_name, limit=10)
    
    print(f"Result messages for {tool_name}:")
    print()
    
    for msg in messages:
        success = msg['success'] == 'true'
        emoji = "✅" if success else "❌"
        print(f"{emoji} {msg['message']}")
        print(f"   Count: {msg['count']}")
        print(f"   Last seen: {msg['last_seen']}")
        print()
    
    # Get overall stats
    stats = get_tool_stats(lakebase, tool_name=tool_name)
    if stats:
        stat = stats[0]
        print(f"\nOverall {tool_name} statistics:")
        print(f"  Total calls: {stat['total_calls']}")
        print(f"  Success: {stat['success_count']}")
        print(f"  Errors: {stat['error_count']}")
        print(f"  Success rate: {stat['success_rate']:.2f}%")
        print(f"  Avg duration: {stat['avg_duration_ms']:.2f}ms")


def demo_session_analysis():
    """Analyze sessions and user activity."""
    print_section("6. Session Analysis")
    
    # Get recent sessions
    sessions = lakebase.run_query("""
        SELECT 
            session_id,
            MAX(user_email) as user_email,
            COUNT(*) as total_calls,
            MIN(timestamp) as session_start,
            MAX(timestamp) as session_end,
            SUM(CASE WHEN (result->>'success')::boolean = true THEN 1 ELSE 0 END) as successful,
            SUM(CASE WHEN (result->>'success')::boolean = false THEN 1 ELSE 0 END) as failed
        FROM mcp_traces
        GROUP BY session_id
        ORDER BY session_start DESC
        LIMIT 5
    """)
    
    print("Recent sessions:")
    print()
    
    for session in sessions:
        print(f"Session: {session['session_id'][:8]}...")
        print(f"  User: {session['user_email']}")
        print(f"  Calls: {session['total_calls']} (✅ {session['successful']}, ❌ {session['failed']})")
        print(f"  Started: {session['session_start']}")
        print(f"  Ended: {session['session_end']}")
        print()


def demo_standardized_result_queries():
    """Show how to query the standardized result structure."""
    print_section("7. Querying Standardized Results (SQL)")
    
    print("Example SQL queries you can run:\n")
    
    queries = [
        (
            "Get success rate from result.success field",
            """
            SELECT 
                tool_name,
                COUNT(*) as total,
                SUM(CASE WHEN (result->>'success')::boolean = true THEN 1 ELSE 0 END) as successful,
                ROUND(100.0 * SUM(CASE WHEN (result->>'success')::boolean = true THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
            FROM mcp_traces
            GROUP BY tool_name;
            """
        ),
        (
            "Find all error messages",
            """
            SELECT 
                tool_name,
                result->>'message' as error_message,
                COUNT(*) as count
            FROM mcp_traces
            WHERE (result->>'success')::boolean = false
            GROUP BY tool_name, result->>'message'
            ORDER BY count DESC;
            """
        ),
        (
            "View recent traces with parsed results",
            """
            SELECT 
                timestamp,
                tool_name,
                result->>'success' as success,
                result->>'message' as message,
                duration_ms
            FROM mcp_traces
            ORDER BY timestamp DESC
            LIMIT 20;
            """
        )
    ]
    
    for i, (description, query) in enumerate(queries, 1):
        print(f"{i}. {description}:")
        print("```sql")
        print(query.strip())
        print("```\n")


def main():
    """Run all demo functions."""
    print("\n" + "#"*70)
    print("  MCP Tracing Framework - Practical Examples")
    print("  Standardized Logging with Result Analysis")
    print("#"*70)
    
    try:
        demo_basic_queries()
        demo_success_rates()
        demo_failure_analysis()
        demo_performance_analysis()
        demo_tool_specific_analysis('get_quote')
        demo_session_analysis()
        demo_standardized_result_queries()
        
        print("\n" + "="*70)
        print("  ✅ Demo complete!")
        print("="*70)
        print("\nNext steps:")
        print("  1. Explore traces with: python tracing_example.py")
        print("  2. Build custom queries using query_traces.py functions")
        print("  3. Create a Databricks dashboard for real-time monitoring")
        print("  4. Set up alerts for high error rates or slow operations")
        print()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure:")
        print("  1. The mcp_traces table exists (run create_mcp_traces_table.sql)")
        print("  2. The MCP server has been running and generating traces")
        print("  3. lakebase.py is properly configured")


if __name__ == "__main__":
    main()
