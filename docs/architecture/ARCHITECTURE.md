# Polymarket Bot - Architecture Standard

**Last Updated**: 2026-01-31
**Version**: 1.0
**Status**: MANDATORY - All code changes must follow these standards

---

## 🎯 Core Principles

### 1. **Fail-Safe, Not Fail-Silent**
- Never use bare `except: pass` - always log errors
- Return explicit error states instead of `None` without context
- Use structured error responses: `{'success': bool, 'error': str, 'data': any}`

### 2. **Thread-Safe by Default**
- All shared mutable state MUST be protected with locks
- Use `threading.Lock()` for dict/list writes from multiple threads
- Document thread-safety in docstrings

### 3. **Resilient API Calls**
- All external API calls MUST have timeouts (10s default)
- All network calls MUST have retry logic with exponential backoff
- Use `@retry_api_call` decorator for all API methods

### 4. **Cache Expiration**
- All caches MUST have explicit expiration logic
- Document cache lifetime in docstring
- Clear caches when data becomes stale

### 5. **UTC Always**
- All datetime operations use `datetime.now(timezone.utc)`
- Never use `datetime.now()` without timezone
- All timestamps stored/compared in UTC

### 6. **Observability First**
- Log all state transitions
- Include context in all error messages (coin, market_id, timestamps)
- Use structured logging format: `[LEVEL] Component: Message (key1=value1, key2=value2)`

---

## 📐 Mandatory Patterns

### Pattern 1: API Call with Retry

**BAD** ❌
```python
def fetch_data(url):
    response = requests.get(url)  # No timeout, no retry
    return response.json()
```

**GOOD** ✅
```python
@retry_api_call(max_retries=3, initial_delay=1.0)
def _fetch_data_from_api(self, url):
    """Fetch data with automatic retry logic"""
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()

def fetch_data(self, url):
    """Public method with error handling"""
    try:
        return self._fetch_data_from_api(url)
    except Exception as e:
        print(f"[ERROR] Failed to fetch {url}: {e}")
        return None
```

---

### Pattern 2: Thread-Safe Shared State

**BAD** ❌
```python
predictions = {}

def monitor_coin(coin):
    predictions[coin] = compute_prediction()  # Race condition!
```

**GOOD** ✅
```python
predictions = {}
predictions_lock = Lock()

def monitor_coin(coin):
    result = compute_prediction()
    with predictions_lock:
        predictions[coin] = result
```

---

### Pattern 3: Cache with Expiration

**BAD** ❌
```python
def __init__(self):
    self.cache = {}  # Never expires!

def get_data(self, key):
    if key in self.cache:
        return self.cache[key]
    # Fetch and cache...
```

**GOOD** ✅
```python
def __init__(self):
    self.cache = {}
    self.cache_expiry = {}
    self.cache_ttl = 900  # 15 minutes

def clear_cache(self):
    """Clear all cached data"""
    self.cache.clear()
    self.cache_expiry.clear()
    print("  [CACHE] Cache cleared")

def get_data(self, key):
    """Get data with automatic expiration"""
    if key in self.cache:
        # Check expiration
        if time.time() < self.cache_expiry.get(key, 0):
            return self.cache[key]
        else:
            # Expired
            del self.cache[key]
            del self.cache_expiry[key]

    # Fetch and cache
    data = self._fetch_data(key)
    self.cache[key] = data
    self.cache_expiry[key] = time.time() + self.cache_ttl
    return data
```

---

### Pattern 4: Structured Error Response

**BAD** ❌
```python
def validate_market(coin):
    try:
        # validation logic
        return True  # What about error details?
    except:
        return False  # No context!
```

**GOOD** ✅
```python
def validate_market(coin):
    """
    Validate market mechanics

    Returns:
        dict: {
            'valid': bool,
            'yes_price': float,
            'no_price': float,
            'deviation': float,
            'error': str or None
        }
    """
    try:
        tokens = self.get_token_ids(coin)
        if not tokens:
            return {
                'valid': False,
                'yes_price': None,
                'no_price': None,
                'deviation': None,
                'error': f'Tokens not found for {coin}'
            }

        yes_price = self.get_midpoint_price(tokens['yes'])
        no_price = self.get_midpoint_price(tokens['no'])

        if yes_price is None or no_price is None:
            return {
                'valid': False,
                'yes_price': yes_price,
                'no_price': no_price,
                'deviation': None,
                'error': f'Prices unavailable (YES={yes_price}, NO={no_price})'
            }

        deviation = abs((yes_price + no_price) - 1.0)

        return {
            'valid': deviation < 0.01,
            'yes_price': yes_price,
            'no_price': no_price,
            'deviation': deviation,
            'error': None
        }
    except Exception as e:
        print(f"[ERROR] Exception validating {coin}: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return {
            'valid': False,
            'yes_price': None,
            'no_price': None,
            'deviation': None,
            'error': f'{type(e).__name__}: {str(e)}'
        }
```

---

### Pattern 5: UTC Datetime

**BAD** ❌
```python
now = datetime.now()  # Local time - timezone issues!
timestamp = datetime.now()  # Ambiguous
```

**GOOD** ✅
```python
from datetime import datetime, timezone

now = datetime.now(timezone.utc)  # Always UTC
timestamp = datetime.now(timezone.utc)

# When parsing ISO strings
start_time = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
```

---

### Pattern 6: Diagnostic Error Messages

**BAD** ❌
```python
print(f"Error: Market not found")
```

**GOOD** ✅
```python
print(f"[ERROR] {coin}: Market not found")
print(f"        Checked {len(markets)} markets")
print(f"        Current UTC: {now.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"        Search terms: {search_terms}")
if coin in cache:
    print(f"        Market ID: {cache[coin].get('id')}")
else:
    print(f"        Market not in cache (cache has: {list(cache.keys())})")
```

---

## 🔒 Required Code Guards

### 1. All API Calls

```python
# MUST have timeout
response = requests.get(url, timeout=10)

# MUST have retry decorator
@retry_api_call(max_retries=3)
def _api_method(self):
    pass
```

### 2. All Shared Mutable State

```python
# MUST have lock
data_lock = Lock()

def update_data(key, value):
    with data_lock:
        self.data[key] = value
```

### 3. All Cache Access

```python
# MUST have clear_cache() method
def clear_cache(self):
    """Clear all cached data for new round"""
    self.cache.clear()
    print("  [CACHE] {CacheName} cache cleared")
```

### 4. All Exception Handlers

```python
# MUST NOT be bare except
try:
    risky_operation()
except SpecificException as e:
    print(f"[ERROR] Context: {e}")
    # Handle or re-raise
```

### 5. All datetime Operations

```python
# MUST use UTC
from datetime import datetime, timezone

now = datetime.now(timezone.utc)
```

---

## 📁 File Structure Standards

### Module Organization

```
src/
├── core/           # Core trading infrastructure
│   ├── polymarket.py      # API client (with retry logic)
│   ├── market_15m.py      # Market operations (with cache expiration)
│   └── price_feed.py      # Real-time price feeds (with graceful shutdown)
├── ml/             # Machine learning
│   ├── model.py           # ML model
│   └── learning.py        # Continuous learning
├── trading/        # Trading logic
│   └── strategy.py        # Bet sizing strategy
├── analysis/       # Market analysis
│   └── arbitrage.py       # Arbitrage detection
└── bot.py          # Main orchestration (with thread safety)
```

### Class Structure Template

```python
"""
Module docstring explaining purpose and key components
"""

import statements  # Standard library first, then third-party, then local

from datetime import datetime, timezone  # Always import timezone
from threading import Lock  # If using threads
from typing import Dict, Optional, List  # Type hints


class ComponentName:
    """
    Component purpose and responsibilities

    Thread Safety: [Document if methods are thread-safe]
    Cache Lifetime: [Document cache expiration policy]
    """

    def __init__(self, dependencies):
        """
        Initialize component

        Args:
            dependencies: Description
        """
        # Caches with expiration
        self.cache = {}

        # Thread safety
        self.lock = Lock()

        # Configuration
        self.timeout = 10
        self.max_retries = 3

    def clear_cache(self):
        """Clear all cached data"""
        self.cache.clear()
        print("  [CACHE] ComponentName cache cleared")

    @retry_api_call(max_retries=3)
    def _fetch_from_api(self, url: str) -> dict:
        """
        Helper method for API calls (private, decorated with retry)

        Args:
            url: API endpoint

        Returns:
            dict: API response

        Raises:
            requests.RequestException: On API failure after retries
        """
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def public_method(self, param: str) -> Dict:
        """
        Public method with error handling

        Args:
            param: Description

        Returns:
            dict: {
                'success': bool,
                'data': any,
                'error': str or None
            }
        """
        try:
            result = self._internal_logic(param)
            return {
                'success': True,
                'data': result,
                'error': None
            }
        except Exception as e:
            print(f"[ERROR] ComponentName.public_method({param}): {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'data': None,
                'error': f'{type(e).__name__}: {str(e)}'
            }
```

---

## 🧪 Testing Standards

### Unit Test Template

```python
import unittest
from datetime import datetime, timezone

class TestComponentName(unittest.TestCase):
    """Test ComponentName functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.component = ComponentName()

    def tearDown(self):
        """Clean up after tests"""
        self.component.clear_cache()

    def test_successful_operation(self):
        """Test normal operation"""
        result = self.component.method()
        self.assertTrue(result['success'])
        self.assertIsNotNone(result['data'])
        self.assertIsNone(result['error'])

    def test_error_handling(self):
        """Test error handling"""
        result = self.component.method_with_invalid_input()
        self.assertFalse(result['success'])
        self.assertIsNone(result['data'])
        self.assertIsNotNone(result['error'])

    def test_thread_safety(self):
        """Test thread-safe operations"""
        from threading import Thread

        threads = []
        for i in range(10):
            thread = Thread(target=self.component.concurrent_method, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Verify no data corruption
        self.assertEqual(len(self.component.data), 10)

    def test_cache_expiration(self):
        """Test cache expiration logic"""
        # Add data to cache
        self.component.get_data('key1')
        self.assertIn('key1', self.component.cache)

        # Clear cache
        self.component.clear_cache()
        self.assertNotIn('key1', self.component.cache)
```

---

## 🔍 Code Review Checklist

Before submitting any code change, verify:

### API Calls
- [ ] Has `timeout=10` parameter
- [ ] Uses `@retry_api_call` decorator or manual retry logic
- [ ] Has try/except with specific exceptions
- [ ] Logs errors with context

### Thread Safety
- [ ] Shared mutable state protected with `Lock()`
- [ ] No race conditions in parallel operations
- [ ] Thread safety documented in docstring

### Caching
- [ ] Cache has `clear_cache()` method
- [ ] Cache expiration logic implemented
- [ ] Cache cleared at appropriate times

### Error Handling
- [ ] No bare `except:` blocks
- [ ] Structured error responses with context
- [ ] Error messages include diagnostic info
- [ ] Tracebacks printed for debugging

### Datetime
- [ ] All `datetime.now()` uses `timezone.utc`
- [ ] ISO string parsing handles 'Z' correctly
- [ ] No mixing of local and UTC times

### Logging
- [ ] All state changes logged
- [ ] Error messages include: component, operation, parameters, error type
- [ ] Success messages confirm operation completed

### Documentation
- [ ] Docstring explains purpose
- [ ] Args and Returns documented
- [ ] Thread safety noted
- [ ] Cache lifetime noted

---

## 🚨 Anti-Patterns to Avoid

### ❌ Silent Failures
```python
# BAD
try:
    risky_operation()
except:
    pass  # Error disappeared!
```

### ❌ Bare Exceptions
```python
# BAD
except Exception as e:
    pass  # What happened?
```

### ❌ No Timeout
```python
# BAD
response = requests.get(url)  # Can hang forever!
```

### ❌ Race Conditions
```python
# BAD
def thread_worker():
    shared_dict['key'] = value  # Unsafe!
```

### ❌ Stale Caches
```python
# BAD
self.cache = {}  # Never cleared, grows forever
```

### ❌ Local Time
```python
# BAD
now = datetime.now()  # Timezone issues!
```

### ❌ Generic Errors
```python
# BAD
print("Error occurred")  # No context!
```

---

## 📊 Metrics to Monitor

Track these metrics to ensure architecture compliance:

1. **API Success Rate**: Should be >95% with retry logic
2. **Cache Hit Rate**: Should show cache is being used
3. **Thread Contention**: Lock wait times should be minimal
4. **Error Context**: All errors should have diagnostic info
5. **Round Success Rate**: Should be >90%

---

## 🔄 Migration Guide

When updating existing code to follow standards:

### Step 1: Add Retry Logic
```python
# Find all API calls
grep -r "requests.get\|requests.post" src/

# Add @retry_api_call decorator to each
```

### Step 2: Add Thread Safety
```python
# Find all shared mutable state
# Add Lock() and with lock: blocks
```

### Step 3: Add Cache Expiration
```python
# Find all self.cache = {}
# Add clear_cache() method
# Call at appropriate times
```

### Step 4: Fix Datetime
```python
# Find all datetime.now()
# Replace with datetime.now(timezone.utc)
```

### Step 5: Improve Error Messages
```python
# Find all except blocks
# Add context to print statements
```

---

## 📚 Required Reading

All contributors must read:
1. This document (ARCHITECTURE.md)
2. Python threading docs: https://docs.python.org/3/library/threading.html
3. Requests timeout docs: https://requests.readthedocs.io/en/latest/user/advanced/#timeouts
4. Datetime timezone docs: https://docs.python.org/3/library/datetime.html#datetime.timezone

---

## ✅ Acceptance Criteria

Code is considered compliant when:

1. ✅ All API calls have timeouts and retry logic
2. ✅ All shared state is thread-safe
3. ✅ All caches have expiration
4. ✅ All errors provide diagnostic context
5. ✅ All datetime uses UTC
6. ✅ All tests pass
7. ✅ Code review checklist complete

---

**This is a living document. Update as architecture evolves.**
