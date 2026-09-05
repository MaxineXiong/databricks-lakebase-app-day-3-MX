# Cryptocurrency Support in Alpaca MCP Server

The Alpaca MCP Server now fully supports cryptocurrency trading alongside traditional stocks!

## Supported Cryptocurrencies

Any cryptocurrency pair ending with "USD" is supported, including:
- **BTCUSD** - Bitcoin
- **ETHUSD** - Ethereum
- **SOLUSD** - Solana
- **ADAUSD** - Cardano
- **DOGEUSD** - Dogecoin
- And many more!

## What Changed

### 1. **alpaca_broker.py**
- ✅ Added `CryptoHistoricalDataClient` for fetching crypto quotes
- ✅ Added `_is_crypto_symbol()` helper to detect crypto symbols
- ✅ Updated `get_quote()` to handle both stocks and crypto
- ✅ Enhanced `place_order()` to use GTC (Good-Til-Canceled) time-in-force for crypto orders
- ✅ Returns `asset_type` field ("stock" or "crypto") in quote responses

### 2. **massive_broker.py**
- ✅ Added `_is_crypto_symbol()` helper
- ✅ Updated `get_quote()` to support crypto symbols using Massive.com's `X:` prefix (e.g., `X:BTCUSD`)
- ✅ Returns `asset_type` field in responses
- ✅ Updated module documentation

### 3. **alpaca_mcp_server.py**
- ✅ Updated all tool docstrings to mention crypto support:
  - `get_quote()` - Get quotes for stocks or crypto
  - `stage_trade()` - Stage trades for stocks or crypto
  - `execute_trade()` - Execute trades for stocks or crypto
  - `add_to_watchlist()` - Add stocks or crypto to watchlist
- ✅ Updated module-level documentation

## How It Works

### Symbol Detection
The system automatically detects cryptocurrency symbols using this rule:
- **Crypto**: Symbols ending with "USD" and longer than 3 characters (e.g., BTCUSD, ETHUSD)
- **Stock**: Everything else (e.g., AAPL, TSLA, F)

### Trading Differences

| Feature | Stocks | Crypto |
|---------|--------|--------|
| Time-in-Force | DAY | GTC (Good-Til-Canceled) |
| Market Hours | 9:30 AM - 4:00 PM ET | 24/7 |
| Quote Source | Massive.com (regular ticker) | Massive.com (X: prefix) |
| Data API | StockHistoricalDataClient | CryptoHistoricalDataClient |

### API Endpoints

**Massive.com Quote Endpoints:**
- Stocks: `GET /v2/aggs/ticker/{symbol}/prev` (e.g., AAPL)
- Crypto: `GET /v2/aggs/ticker/X:{symbol}/prev` (e.g., X:BTCUSD)

**Alpaca Data APIs:**
- Stocks: `StockHistoricalDataClient.get_stock_latest_quote()`
- Crypto: `CryptoHistoricalDataClient.get_crypto_latest_quote()`

## Example Usage

### Get Bitcoin Quote
```python
quote = get_quote("BTCUSD")
# Returns:
# {
#   "symbol": "BTCUSD",
#   "price": 42000.50,
#   "as_of": "2025-01-01T12:00:00",
#   "volume": 1234567,
#   "change": 500.25,
#   "change_percent": 1.2,
#   "asset_type": "crypto"
# }
```

### Stage a Bitcoin Trade
```python
staged = stage_trade("BTCUSD", "BUY", 0.5)
# Returns confirmation code and estimated cost
```

### Execute the Trade
```python
result = execute_trade(
    account_id="paper",
    symbol="BTCUSD",
    side="BUY",
    quantity=0.5,
    confirmation_code="12345"  # From stage_trade
)
```

### Add to Watchlist
```python
add_to_watchlist("ETHUSD")
# Ethereum is now in your watchlist!
```

## Testing

To test cryptocurrency support:

1. **Get a crypto quote:**
   ```bash
   curl -X POST http://localhost:8000/mcp/v1/tools/get_quote \
     -H "Content-Type: application/json" \
     -d '{"symbol": "BTCUSD"}'
   ```

2. **Stage a crypto trade:**
   ```bash
   curl -X POST http://localhost:8000/mcp/v1/tools/stage_trade \
     -H "Content-Type: application/json" \
     -d '{"symbol": "BTCUSD", "side": "BUY", "quantity": 0.1}'
   ```

3. **Check positions (will show crypto holdings):**
   ```bash
   curl -X POST http://localhost:8000/mcp/v1/tools/get_positions \
     -H "Content-Type: application/json" \
     -d '{"account_id": "paper"}'
   ```

## Important Notes

* ⚠️ **Crypto trading is 24/7** - Unlike stocks, crypto markets never close
* ⚠️ **Fractional quantities are supported** - You can buy 0.001 BTC
* ⚠️ **GTC orders for crypto** - Crypto orders use Good-Til-Canceled (GTC) time-in-force
* ✅ **All existing tools work** - No API changes needed for crypto
* ✅ **Tracing included** - All crypto trades are traced to `mcp_traces` table

## Compatibility

All existing MCP tools work seamlessly with cryptocurrency symbols:

- ✅ `get_quote(symbol)` - Works for both stocks and crypto
- ✅ `stage_trade(symbol, side, quantity)` - Works for both
- ✅ `execute_trade(account_id, symbol, side, quantity, confirmation_code)` - Works for both
- ✅ `get_positions(account_id)` - Shows both stock and crypto positions
- ✅ `get_account_summary(account_id)` - Includes crypto in total equity
- ✅ `add_to_watchlist(symbol)` - Track both stocks and crypto
- ✅ `vector_search(query)` - Search news for both asset types

## Next Steps

1. Restart your MCP server to load the new crypto support
2. Try getting a quote for BTCUSD or ETHUSD
3. Test staging and executing a small crypto trade
4. Check your portfolio with `get_positions()` and `get_account_summary()`

Happy crypto trading! 🚀
