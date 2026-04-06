# Architecture Quick Reference

**One-page cheat sheet for compliant code**

---

## ⚡ Quick Patterns

### API Call
```python
@retry_api_call(max_retries=3)
def _fetch(self, url):
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()
```

### Thread Safety
```python
data_lock = Lock()

def update(key, value):
    with data_lock:
        self.data[key] = value
```

### Cache
```python
def clear_cache(self):
    self.cache.clear()
    print("  [CACHE] Cache cleared")
```

### Error Response
```python
return {
    'success': bool,
    'data': any,
    'error': str or None
}
```

### Datetime
```python
from datetime import datetime, timezone
now = datetime.now(timezone.utc)
```

---

## 🚫 What NOT to Do

| ❌ BAD | ✅ GOOD |
|--------|---------|
| `requests.get(url)` | `requests.get(url, timeout=10)` |
| `except:` | `except Exception as e:` |
| `datetime.now()` | `datetime.now(timezone.utc)` |
| `data[key] = value` (in threads) | `with lock: data[key] = value` |
| `print("Error")` | `print(f"[ERROR] {component}: {error} (key={key})")` |
| `return None` | `return {'success': False, 'error': 'reason'}` |

---

## 📋 Pre-Commit Checklist

Before committing:
- [ ] API calls have `timeout=10`
- [ ] No `except:` without exception type
- [ ] All `datetime.now()` use `timezone.utc`
- [ ] Shared state protected with `Lock()`
- [ ] Caches have `clear_cache()` method
- [ ] Errors have diagnostic context
- [ ] Tests pass

Run: `python scripts/check_architecture.py --all src/**/*.py`

---

## 🛠️ Tools

### Generate Template
```bash
python scripts/generate_template.py --class MyComponent > src/my_component.py
python scripts/generate_template.py --test MyComponent > tests/test_my_component.py
```

### Check Compliance
```bash
# Check single file
python scripts/check_architecture.py --all src/bot.py

# Check all files
python scripts/check_architecture.py --all src/**/*.py
```

### Setup Pre-Commit Hooks
```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

---

## 📊 Log Format

```
[LEVEL] Component: Message (key1=value1, key2=value2)
```

Examples:
```
[ERROR] MarketFinder: Market not found (coin=BTC, markets_checked=50, time=14:00:00)
[OK] Validator: Market valid (coin=ETH, yes_price=0.520, no_price=0.480)
[RETRY] API._fetch timeout, retrying in 2.0s (attempt 2/3)
[CACHE] MarketCache cleared
```

---

## 🔍 Common Patterns

### Method Structure
```python
def public_method(self, param: str) -> dict:
    """
    Brief description

    Args:
        param: Description

    Returns:
        dict: {'success': bool, 'data': any, 'error': str}
    """
    try:
        result = self._internal_logic(param)
        return {
            'success': True,
            'data': result,
            'error': None
        }
    except Exception as e:
        print(f"[ERROR] Component.method({param}): {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'data': None,
            'error': f'{type(e).__name__}: {str(e)}'
        }
```

### Validation Pattern
```python
def validate(self, data: dict) -> dict:
    """Validate data"""
    try:
        if not data:
            return {
                'valid': False,
                'error': 'Data is empty'
            }

        # Validation logic
        issues = []
        if 'field' not in data:
            issues.append("Missing field")

        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'error': None if len(issues) == 0 else 'Validation failed'
        }
    except Exception as e:
        return {
            'valid': False,
            'issues': [],
            'error': str(e)
        }
```

---

## 🎯 When to Use Each Pattern

| Situation | Pattern |
|-----------|---------|
| Calling external API | `@retry_api_call` + `timeout=10` |
| Multiple threads write shared data | `Lock()` + `with lock:` |
| Data needs periodic refresh | Cache with `clear_cache()` |
| Returning status from method | Structured dict response |
| Working with time | UTC datetime |
| Logging errors | Include context (component, operation, params) |

---

## 📚 Full Documentation

- Complete guide: `ARCHITECTURE.md`
- Setup: `SETUP.md`
- Code review: `ARCHITECTURE.md#code-review-checklist`

---

## ⚙️ VSCode Snippets

Add to `.vscode/polymarket.code-snippets`:

```json
{
  "API Method": {
    "prefix": "api-method",
    "body": [
      "@retry_api_call(max_retries=3)",
      "def _fetch_${1:data}(self, ${2:param}: str) -> dict:",
      "    \"\"\"Fetch ${1:data} from API\"\"\"",
      "    response = requests.get(f\"${3:url}\", timeout=10)",
      "    response.raise_for_status()",
      "    return response.json()"
    ]
  },
  "Thread-Safe Update": {
    "prefix": "thread-safe",
    "body": [
      "with self.${1:data}_lock:",
      "    self.${1:data}[${2:key}] = ${3:value}"
    ]
  },
  "Structured Response": {
    "prefix": "struct-response",
    "body": [
      "return {",
      "    'success': ${1:True},",
      "    'data': ${2:result},",
      "    'error': ${3:None}",
      "}"
    ]
  }
}
```

---

**Keep this handy while coding!**
