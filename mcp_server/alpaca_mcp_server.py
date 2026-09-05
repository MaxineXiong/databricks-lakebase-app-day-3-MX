"""
Alpaca Markets paper-trading MCP server.

Exposes paper-trading tools over MCP (Model Context Protocol) so a
Databricks Agent Bricks agent can call them like any other tool:
    - get_quote(symbol)  # Supports stocks (AAPL) and crypto (BTCUSD)
    - stage_trade(symbol, side, quantity)
    - execute_trade(account_id, symbol, side, quantity, confirmation_code)
    - get_positions(account_id)
    - get_account_summary(account_id)
    - get_order_history(account_id, limit)
    - get_balance(account_id)
    - get_current_user()

These tools are backed by Alpaca Markets' real, hosted paper-trading
account (see alpaca_broker.py), so students can safely wire an Agent
Bricks agent to place real (but fake-money) trades without a real
brokerage account or risk of real money moving. account_id is accepted
for signature compatibility but is not used to select an account - Alpaca
paper trading is one account per API key pair.

Cryptocurrency Support: Both stocks (e.g., AAPL, TSLA) and cryptocurrencies
(e.g., BTCUSD, ETHUSD, SOLUSD) are supported. Crypto symbols end with USD.

Tracing: All tool invocations are automatically traced to the Lakebase
mcp_traces table, capturing parameters, results, duration, and a unique
session ID per server instance. See TRACING_README.md for setup and usage.

Swap-in-a-real-broker note: to point this at a different broker instead,
keep the same 5 tool signatures below and replace the alpaca_broker.*
calls inside each tool with calls to that broker's SDK/API - the MCP
surface for the agent does not need to change. The original Lakebase-
simulated engine is preserved in paper_broker.py for reference.

Deploy this as its own Databricks App (same app.yaml + FastMCP entrypoint
pattern documented at
https://docs.databricks.com/aws/en/agents/mcp-tools/custom-mcp), separate
from the dashboard app, so an Agent Bricks agent (or any MCP client) can
register its URL as an external MCP server.

Run locally:
    python alpaca_mcp_server.py
"""

import os
import logging
import random
import uuid
import time
import json
from contextvars import ContextVar
from functools import wraps

from fastmcp import FastMCP
from sentence_transformers import SentenceTransformer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

import alpaca_broker
import massive_broker
import lakebase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("alpaca-mcp-server")

# In-memory storage for staged trades (confirmation codes)
_staged_trades = {}

# Session tracking - generate a unique session ID per server instance
_session_id = str(uuid.uuid4())

# Load embedding model once at startup
_embedding_model = None

def get_embedding_model():
    """Lazy-load the embedding model (expensive operation, only on first use)."""
    global _embedding_model
    if _embedding_model is None:
        logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    return _embedding_model

# Table names from environment variables
NEWS_TABLE_NAME = os.environ.get("NEWS_TABLE_NAME", "ticker_news_documents")
EMBEDDINGS_TABLE_NAME = os.environ.get("EMBEDDINGS_TABLE_NAME", "ticker_news_embeddings")
CHUNK_EMBEDDINGS_TABLE_NAME = os.environ.get("CHUNK_EMBEDDINGS_TABLE_NAME", "ticker_news_chunk_embeddings")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

# Context variable to store request headers for accessing end-user identity
_request_context: ContextVar[dict] = ContextVar('request_context', default={})


def _get_end_user_email() -> str:
    """Get the actual end user's email from request headers, or fallback to service principal."""
    # Try to get from X-Forwarded-User header (Databricks App context)
    headers = _request_context.get()
    forwarded_user = headers.get('x-forwarded-user')
    if forwarded_user:
        return forwarded_user
    
    # Fallback: use service principal (local development or non-App contexts)
    from databricks.sdk import WorkspaceClient
    w = WorkspaceClient()
    return w.current_user.me().user_name or 'maxinexiong2@gmail.com'


def _create_standardized_result(tool_name: str, raw_result: any, error: Exception = None) -> dict:
    """
    Create a standardized result structure for tracing.
    
    Args:
        tool_name: Name of the tool that was called
        raw_result: The raw result returned by the tool
        error: Exception if the tool raised an error
    
    Returns:
        Standardized result dict with: tool_name, success, message, data
    """
    if error:
        # Exception was raised
        return {
            "tool_name": tool_name,
            "success": False,
            "message": f"Exception raised: {str(error)}",
            "data": None
        }
    
    # Check if result has a status field (common pattern in our tools)
    if isinstance(raw_result, dict):
        result_status = raw_result.get("status", "unknown")
        
        if result_status == "error":
            # Tool returned an error status
            message = raw_result.get("message", "Tool execution failed")
            return {
                "tool_name": tool_name,
                "success": False,
                "message": message,
                "data": raw_result
            }
        elif result_status == "success":
            # Tool returned success status
            message = raw_result.get("message", f"Successfully executed {tool_name}")
            return {
                "tool_name": tool_name,
                "success": True,
                "message": message,
                "data": raw_result
            }
        elif result_status == "not_found":
            # Special case: not found (considered a handled failure)
            message = raw_result.get("message", "Resource not found")
            return {
                "tool_name": tool_name,
                "success": False,
                "message": message,
                "data": raw_result
            }
    
    # No status field or not a dict - assume success if we got here without exception
    return {
        "tool_name": tool_name,
        "success": True,
        "message": f"Successfully executed {tool_name}",
        "data": raw_result
    }


def _log_trace(tool_name: str, parameters: dict, result: any, duration_ms: float, status: str, error_message: str = None):
    """
    Log a tool invocation trace to Lakebase.
    
    Args:
        tool_name: Name of the tool that was called
        parameters: Input parameters (will be JSON serialized)
        result: Standardized result dict (will be JSON serialized)
        duration_ms: Execution duration in milliseconds
        status: 'success' or 'error' (reflects actual tool execution status)
        error_message: Error message if status is 'error'
    """
    try:
        trace_id = str(uuid.uuid4())
        user_email = _get_end_user_email()
        
        # Serialize parameters and result to JSON
        params_json = json.dumps(parameters) if parameters else None
        result_json = json.dumps(result) if result else None
        
        sql = """
        INSERT INTO mcp_traces (
            trace_id, session_id, timestamp, tool_name, parameters, 
            result, user_email, duration_ms, status, error_message
        )
        VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s)
        """
        
        lakebase.run_write(
            sql,
            (
                trace_id,
                _session_id,
                tool_name,
                params_json,
                result_json,
                user_email,
                duration_ms,
                status,
                error_message
            )
        )
        
        logger.info(f"Traced {tool_name} call: {trace_id} (session: {_session_id})")
    except Exception as e:
        # Don't let tracing failures break the tool call
        logger.exception(f"Failed to log trace for {tool_name}")


def trace_tool(func):
    """
    Decorator to automatically trace MCP tool calls with standardized result format.
    
    Captures input parameters, creates a standardized result structure, and determines
    the actual execution status from the tool's return value.
    
    Standardized result format:
    {
        "tool_name": str,
        "success": bool,
        "message": str,
        "data": any
    }
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        tool_name = func.__name__
        start_time = time.time()
        
        # Capture parameters (combine positional and keyword args)
        import inspect
        sig = inspect.signature(func)
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()
        parameters = dict(bound_args.arguments)
        
        try:
            # Execute the tool
            raw_result = func(*args, **kwargs)
            duration_ms = (time.time() - start_time) * 1000
            
            # Create standardized result
            standardized_result = _create_standardized_result(tool_name, raw_result)
            
            # Determine status from the standardized result
            status = 'success' if standardized_result['success'] else 'error'
            error_message = None if standardized_result['success'] else standardized_result['message']
            
            # Log trace with standardized result
            _log_trace(
                tool_name=tool_name,
                parameters=parameters,
                result=standardized_result,
                duration_ms=duration_ms,
                status=status,
                error_message=error_message
            )
            
            # Return the original result (not the standardized one)
            return raw_result
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            # Create standardized error result
            standardized_result = _create_standardized_result(tool_name, None, error=e)
            
            # Log error trace
            _log_trace(
                tool_name=tool_name,
                parameters=parameters,
                result=standardized_result,
                duration_ms=duration_ms,
                status='error',
                error_message=str(e)
            )
            
            # Re-raise the exception
            raise
    
    return wrapper


mcp = FastMCP("alpaca-paper-trading")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware to capture HTTP headers containing end-user identity."""
    async def dispatch(self, request: Request, call_next):
        # Capture headers that Databricks injects with user identity
        headers = {
            'x-forwarded-user': request.headers.get('x-forwarded-user'),
            'x-forwarded-email': request.headers.get('x-forwarded-email'),
        }
        _request_context.set(headers)
        response = await call_next(request)
        return response


@mcp.tool
@trace_tool
def get_quote(symbol: str) -> dict:
    """
    Get the latest real quote for a stock or cryptocurrency symbol from Massive.com.
    
    Supports both stocks (e.g., AAPL, TSLA) and cryptocurrencies (e.g., BTCUSD, ETHUSD).

    Args:
        symbol: Stock ticker symbol (e.g., "AAPL") or crypto pair (e.g., "BTCUSD").

    Returns:
        A dict with symbol, price, as_of (ISO timestamp), volume, change, change_percent, and asset_type.
    """
    return massive_broker.get_quote(symbol)


@mcp.tool
@trace_tool
def stage_trade(symbol: str, side: str, quantity: float, account_id: str = None) -> dict:
    """
    Stage a trade for confirmation. Gets the current quote, calculates cost,
    and generates a 5-digit confirmation code that must be provided to execute_trade.
    
    Supports both stocks (e.g., AAPL) and cryptocurrencies (e.g., BTCUSD).
    
    Args:
        symbol: Stock ticker symbol (e.g., "AAPL") or crypto pair (e.g., "BTCUSD").
        side: "BUY" or "SELL".
        quantity: Number of shares/units to trade (must be positive).
        account_id: Optional account ID (for signature compatibility).
    
    Returns:
        A dict with symbol, side, quantity, current_price, estimated_cost, 
        confirmation_code, and a suggestion message.
    """
    try:
        # Validate inputs
        if side not in ["BUY", "SELL"]:
            return {
                "status": "error",
                "message": "side must be 'BUY' or 'SELL'"
            }
        
        if quantity <= 0:
            return {
                "status": "error",
                "message": "quantity must be positive"
            }
        
        # Get current quote from Massive.com
        quote = massive_broker.get_quote(symbol)
        price = quote["price"]
        estimated_cost = price * quantity
        
        # Generate random 5-digit confirmation code
        confirmation_code = f"{random.randint(10000, 99999)}"
        
        # Store staged trade in memory for validation during place_trade
        _staged_trades[confirmation_code] = {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "estimated_price": price,
            "estimated_cost": estimated_cost
        }
        
        # Generate suggestion message
        action = "buying" if side == "BUY" else "selling"
        suggestion = (
            f"You are {action} {quantity} shares of {symbol} at ${price:.2f} per share. "
            f"Estimated total cost: ${estimated_cost:.2f}. "
            f"To confirm this trade, call execute_trade with confirmation code: {confirmation_code}"
        )
        
        return {
            "status": "success",
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "current_price": price,
            "estimated_cost": estimated_cost,
            "confirmation_code": confirmation_code,
            "suggestion": suggestion,
            "quote_details": quote
        }
        
    except Exception as e:
        logger.exception("Failed to stage trade")
        return {
            "status": "error",
            "message": f"Failed to stage trade: {str(e)}"
        }


@mcp.tool
@trace_tool
def execute_trade(account_id: str, symbol: str, side: str, quantity: float, confirmation_code: str) -> dict:
    """
    Place a real market order (paper trade) - BUY or SELL - against the
    configured Alpaca paper trading account.
    
    Requires a 5-digit confirmation code from stage_trade.
    
    Supports both stocks (e.g., AAPL) and cryptocurrencies (e.g., BTCUSD).

    Args:
        account_id: Accepted for signature compatibility; not used to
            select an account (Alpaca paper trading is one account per
            API key pair).
        symbol: Stock ticker symbol (e.g., "AAPL") or crypto pair (e.g., "BTCUSD").
        side: "BUY" or "SELL".
        quantity: Number of shares/units to trade (must be positive).
        confirmation_code: 5-digit confirmation code from stage_trade.

    Returns:
        A dict describing the order (id, symbol, side, quantity,
        price, notional, status, created_at).
    """
    try:
        # Validate confirmation code and retrieve staged trade from memory
        if confirmation_code not in _staged_trades:
            return {
                "status": "error",
                "message": "Invalid or expired confirmation code. Please use stage_trade first to get a valid code."
            }
        
        staged = _staged_trades[confirmation_code]
        
        # Validate that the trade parameters match the staged trade
        if (staged["symbol"] != symbol or 
            staged["side"] != side or 
            float(staged["quantity"]) != float(quantity)):
            return {
                "status": "error",
                "message": f"Trade parameters do not match staged trade. Expected: {staged['side']} {staged['quantity']} shares of {staged['symbol']}"
            }
        
        # Delete the staged trade (one-time use code)
        del _staged_trades[confirmation_code]
        
        # Execute the actual trade via Alpaca
        result = alpaca_broker.place_order(account_id, symbol, side, quantity)
        
        return result
        
    except Exception as e:
        logger.exception("Failed to place trade")
        return {
            "status": "error",
            "message": f"Failed to place trade: {str(e)}"
        }


@mcp.tool
@trace_tool
def get_positions(account_id: str) -> list[dict]:
    """
    Get all open positions for the Alpaca paper trading account.

    Args:
        account_id: Accepted for signature compatibility; not used to
            select an account.

    Returns:
        A list of dicts, each with symbol, quantity, avg_cost, updated_at.
    """
    return alpaca_broker.get_positions(account_id)


@mcp.tool
@trace_tool
def get_account_summary(account_id: str) -> dict:
    """
    Get a full account summary for the Alpaca paper trading account: cash
    balance, open positions marked-to-market, total market value, and
    total equity (cash + market value).

    Args:
        account_id: Accepted for signature compatibility; not used to
            select an account.

    Returns:
        A dict with account_id, cash_balance, positions, market_value,
        total_equity.
    """
    return alpaca_broker.get_account_summary(account_id)


@mcp.tool
@trace_tool
def get_order_history(account_id: str, limit: int = 50) -> list[dict]:
    """
    Get recent orders for the Alpaca paper trading account, most recent first.

    Args:
        account_id: Accepted for signature compatibility; not used to
            select an account.
        limit: Max number of orders to return (default 50).

    Returns:
        A list of dicts, each with id, symbol, side, quantity, price,
        notional, status, created_at.
    """
    return alpaca_broker.get_order_history(account_id, limit)


@mcp.tool
@trace_tool
def get_balance(account_id: str) -> dict:
    """
    Get the current cash balance and buying power for the Alpaca paper 
    trading account.

    Args:
        account_id: Accepted for signature compatibility; not used to
            select an account.

    Returns:
        A dict with account_id, cash_balance, buying_power, and currency.
    """
    return alpaca_broker.get_account_summary(account_id)


@mcp.tool
@trace_tool
def get_current_user() -> dict:
    """
    Get information about the currently authenticated end user accessing the MCP server.
    
    When running as a Databricks App, this returns the actual end user making the
    request (from X-Forwarded-User header), not the service principal running the app.

    Returns:
        A dict with user_name (email from X-Forwarded-User header), 
        forwarded_email, and source ("request_header" or "service_principal").
    """
    try:
        # First, try to get the end user from the request headers
        # Databricks injects X-Forwarded-User with the actual user's email
        headers = _request_context.get()
        forwarded_user = headers.get('x-forwarded-user')
        forwarded_email = headers.get('x-forwarded-email')
        
        if forwarded_user:
            return {
                "status": "success",
                "user_name": forwarded_user,
                "forwarded_email": forwarded_email,
                "source": "request_header",
            }
        
        # Fallback: return the service principal if headers aren't available
        # (e.g., when running locally or in non-App contexts)
        from databricks.sdk import WorkspaceClient
        w = WorkspaceClient()
        user = w.current_user.me()
        return {
            "status": "success",
            "user_name": user.user_name,
            "display_name": user.display_name,
            "active": user.active,
            "source": "service_principal",
        }
    except Exception as e:
        logger.exception("Failed to get current user")
        return {
            "status": "error",
            "message": f"Failed to get current user: {str(e)}",
        }


@mcp.tool
@trace_tool
def add_to_watchlist(symbol: str, user_email: str = 'maxinexiong2@gmail.com') -> dict:
    """
    Add a stock or cryptocurrency to the watchlist by fetching its current quote
    from Massive.com and storing it in the Lakebase watchlist table.
    
    Supports both stocks (e.g., AAPL) and cryptocurrencies (e.g., BTCUSD).
    
    Uses the authenticated user's email as the user_id.
    
    Args:
        symbol: Stock ticker symbol (e.g., "AAPL") or crypto pair (e.g., "BTCUSD").
    
    Returns:
        A dict with the quote data and confirmation that it was added to the watchlist.
    """
    try:
        # Get the actual end user's email (not the service principal)
        user_email = user_email
        
        # Get quote from Massive.com
        quote = massive_broker.get_quote(symbol)
        
        # Store in Lakebase watchlist table
        sql = """
        INSERT INTO watchlist (email, symbol, latest_price, updated_at)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (email, symbol) 
        DO UPDATE SET 
            latest_price = EXCLUDED.latest_price,
            updated_at = NOW()
        """
        
        lakebase.run_write(
            sql,
            (
                user_email,
                quote["symbol"],
                quote["price"]
            ),
        )
        
        return {
            "status": "success",
            "message": f"Added {symbol} to watchlist for {user_email}",
            "user_email": user_email,
            "quote": quote,
        }
    except Exception as e:
        logger.exception(f"Failed to add {symbol} to watchlist")
        return {
            "status": "error",
            "message": f"Failed to add {symbol} to watchlist: {str(e)}",
        }


@mcp.tool
@trace_tool
def get_watchlist(limit: int = 100, email: str = 'maxinexiong2@gmail.com') -> dict:
    """
    Retrieve all stocks in the authenticated user's watchlist from Lakebase.
    
    Uses the authenticated user's email as the user_id.
    
    Args:
        limit: Maximum number of entries to return (default: 100).
        email: authenticate user's email
    
    Returns:
        A dict with watchlist entries sorted by most recently added.
    """
    try:
        # Get the actual end user's email (not the service principal)
        
        sql = """
        SELECT 
            symbol,
            latest_price,
            updated_at
        FROM watchlist
        WHERE email = %s
        LIMIT %s
        """
        
        rows = lakebase.run_query(sql, (email, limit))
        
        return {
            "status": "success",
            "user_email": email,
            "count": len(rows),
            "watchlist": rows,
        }
    except Exception as e:
        logger.exception(f"Failed to retrieve watchlist")
        return {
            "status": "error",
            "message": f"Failed to retrieve watchlist: {str(e)}",
        }


@mcp.tool
@trace_tool
def remove_from_watchlist(symbol: str) -> dict:
    """
    Remove a stock from the authenticated user's watchlist.
    
    Uses the authenticated user's email as the user_id.
    
    Args:
        symbol: Stock ticker symbol to remove, e.g. "AAPL".
    
    Returns:
        A dict with status and confirmation message.
    """
    try:
        # Get the actual end user's email (not the service principal)
        user_email = _get_end_user_email()
        
        symbol = symbol.strip().upper()
        
        sql = """
        DELETE FROM watchlist
        WHERE email = %s AND symbol = %s
        """
        
        rows_affected = lakebase.run_write(sql, (user_email, symbol))
        
        if rows_affected > 0:
            return {
                "status": "success",
                "message": f"Removed {symbol} from watchlist",
                "symbol": symbol,
                "user_email": user_email,
            }
        else:
            return {
                "status": "not_found",
                "message": f"{symbol} was not in the watchlist",
                "symbol": symbol,
                "user_email": user_email,
            }
    except Exception as e:
        logger.exception(f"Failed to remove {symbol} from watchlist")
        return {
            "status": "error",
            "message": f"Failed to remove {symbol} from watchlist: {str(e)}",
        }


@mcp.tool
@trace_tool
def vector_search(query: str, limit: int = 10, search_chunks: bool = True) -> dict:
    """
    Semantic search over ticker news using vector embeddings.
    
    Accepts a text query, computes its embedding, and returns the most similar
    documents and chunks from Lakebase using pgvector's cosine similarity.
    
    Args:
        query: Natural language search query (e.g. "tech company earnings")
        limit: Maximum number of results to return (default 10)
        search_chunks: Whether to search chunk-level embeddings in addition to documents
    
    Returns:
        A dict with query, documents, chunks, and model name
    """
    if not query or not query.strip():
        return {"error": "Query text is required"}
    
    try:
        # Compute embedding for the query
        model = get_embedding_model()
        query_embedding = model.encode(query)
        
        # Convert to list for JSON serialization and postgres array format
        embedding_list = query_embedding.tolist()
        embedding_str = '[' + ','.join(str(float(x)) for x in embedding_list) + ']'
        
        # Search document-level embeddings
        doc_results = lakebase.run_query(
            f"""
            SELECT 
                e.id,
                e.ticker,
                e.title,
                e.published_utc,
                e.model_name,
                1 - (e.embedding <=> %s::vector) as similarity,
                d.description,
                d.article_url,
                d.sentiment
            FROM {EMBEDDINGS_TABLE_NAME} e
            LEFT JOIN {NEWS_TABLE_NAME} d ON e.id = d.id
            ORDER BY similarity DESC
            LIMIT %s
            """,
            (embedding_str, limit),
        )
        
        chunk_results = []
        if search_chunks:
            # Search chunk-level embeddings
            chunk_results = lakebase.run_query(
                f"""
                SELECT 
                    c.id,
                    c.article_id,
                    c.ticker,
                    c.chunk_index,
                    c.chunk_text,
                    c.model_name,
                    1 - (c.embedding <=> %s::vector) as similarity,
                    d.title,
                    d.article_url,
                    d.published_utc
                FROM {CHUNK_EMBEDDINGS_TABLE_NAME} c
                LEFT JOIN {NEWS_TABLE_NAME} d ON c.article_id = d.id
                ORDER BY similarity DESC
                LIMIT %s
                """,
                (embedding_str, limit),
            )
        
        return {
            "query": query,
            "documents": doc_results,
            "chunks": chunk_results,
            "model": EMBEDDING_MODEL
        }
        
    except Exception as e:
        logger.exception("Vector search failed")
        return {"error": str(e)}


if __name__ == "__main__":
    # Add middleware to capture request headers for end-user identity
    # This must be done before mcp.run() is called
    if hasattr(mcp, 'app') and mcp.app is not None:
        mcp.app.add_middleware(RequestContextMiddleware)
    
    # Databricks Apps route external HTTP traffic to this port via app.yaml;
    # streamable-http is the transport Databricks' MCP client/gateway expects
    # (see the "Host your own MCP" doc linked in the module docstring above).
    port = int(os.getenv("DATABRICKS_APP_PORT", os.getenv("PORT", 8000)))
    mcp.run(transport="http", host="0.0.0.0", port=port)
