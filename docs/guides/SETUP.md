# Architecture Enforcement Setup Guide

**How to install and configure architecture compliance tools**

---

## 📦 Installation

### Step 1: Install Pre-Commit Framework

```bash
pip install pre-commit
```

### Step 2: Install Development Dependencies

```bash
pip install -r requirements-dev.txt
```

Create `requirements-dev.txt`:
```
# Code quality
black==24.1.1
isort==5.13.2
flake8==7.0.0
mypy==1.8.0
types-requests

# Security
bandit==1.7.6

# Testing
pytest==7.4.3
pytest-cov==4.1.0
pytest-mock==3.12.0

# Pre-commit
pre-commit==3.6.0
```

### Step 3: Install Pre-Commit Hooks

```bash
pre-commit install
```

This installs git hooks that run before each commit.

---

## ⚙️ Configuration

### Git Hooks (Automatic)

Once installed, pre-commit hooks run automatically on `git commit`.

To run manually on all files:
```bash
pre-commit run --all-files
```

To run on specific files:
```bash
pre-commit run --files src/bot.py src/core/market_15m.py
```

### VSCode Integration (Recommended)

Add to `.vscode/settings.json`:

```json
{
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true,
  "python.linting.mypyEnabled": true,
  "python.linting.banditEnabled": true,

  "python.formatting.provider": "black",
  "editor.formatOnSave": true,

  "[python]": {
    "editor.codeActionsOnSave": {
      "source.organizeImports": true
    }
  },

  "python.analysis.typeCheckingMode": "basic",

  "files.watcherExclude": {
    "**/.git/objects/**": true,
    "**/.git/subtree-cache/**": true,
    "**/node_modules/*/**": true,
    "**/__pycache__/**": true
  }
}
```

### VSCode Code Snippets

Create `.vscode/polymarket.code-snippets`:

```json
{
  "Compliant Class": {
    "prefix": "poly-class",
    "body": [
      "class ${1:ClassName}:",
      "    \"\"\"",
      "    ${2:Brief description}",
      "",
      "    Thread Safety: ${3:SAFE/UNSAFE}",
      "    Cache Lifetime: ${4:Duration}",
      "    \"\"\"",
      "",
      "    def __init__(self, ${5:dependency}):",
      "        \"\"\"Initialize ${1:ClassName}\"\"\"",
      "        self.${5:dependency} = ${5:dependency}",
      "        self.cache = {}",
      "        self.lock = Lock()",
      "        self.timeout = 10",
      "",
      "    def clear_cache(self):",
      "        \"\"\"Clear all cached data\"\"\"",
      "        with self.lock:",
      "            self.cache.clear()",
      "        print(\"  [CACHE] ${1:ClassName} cache cleared\")"
    ],
    "description": "Architecture-compliant class template"
  },

  "API Method with Retry": {
    "prefix": "poly-api",
    "body": [
      "@retry_api_call(max_retries=3, initial_delay=1.0)",
      "def _fetch_${1:data}(self, ${2:param}: str) -> dict:",
      "    \"\"\"Fetch ${1:data} from API with retry logic\"\"\"",
      "    response = requests.get(",
      "        f\"${3:https://api.example.com}/{${2:param}}\",",
      "        timeout=self.timeout",
      "    )",
      "    response.raise_for_status()",
      "    return response.json()"
    ],
    "description": "API method with retry decorator and timeout"
  },

  "Thread-Safe Dict Update": {
    "prefix": "poly-lock",
    "body": [
      "with self.${1:data}_lock:",
      "    self.${1:data}[${2:key}] = ${3:value}"
    ],
    "description": "Thread-safe dictionary update"
  },

  "Structured Response": {
    "prefix": "poly-response",
    "body": [
      "return {",
      "    'success': ${1:True},",
      "    'data': ${2:result},",
      "    'error': ${3:None}",
      "}"
    ],
    "description": "Structured response dict"
  },

  "Error Handler": {
    "prefix": "poly-error",
    "body": [
      "try:",
      "    ${1:# Operation}",
      "    result = ${2:operation()}",
      "    return {",
      "        'success': True,",
      "        'data': result,",
      "        'error': None",
      "    }",
      "except Exception as e:",
      "    print(f\"[ERROR] ${3:Component}.${4:method}(${5:params}): {type(e).__name__}: {e}\")",
      "    import traceback",
      "    traceback.print_exc()",
      "    return {",
      "        'success': False,",
      "        'data': None,",
      "        'error': f'{type(e).__name__}: {str(e)}'",
      "    }"
    ],
    "description": "Complete error handling pattern"
  },

  "UTC Datetime": {
    "prefix": "poly-datetime",
    "body": [
      "from datetime import datetime, timezone",
      "now = datetime.now(timezone.utc)"
    ],
    "description": "UTC datetime import and usage"
  }
}
```

---

## 🔧 Usage

### Before Committing

```bash
# 1. Format code
black src/

# 2. Sort imports
isort src/

# 3. Check architecture compliance
python scripts/check_architecture.py --all src/**/*.py

# 4. Run tests
pytest tests/ -v

# 5. Commit (pre-commit hooks run automatically)
git add .
git commit -m "Your message"
```

### Generating New Files

```bash
# Generate compliant class
python scripts/generate_template.py --class MyComponent > src/my_component.py

# Generate test file
python scripts/generate_template.py --test MyComponent > tests/test_my_component.py
```

### Manual Compliance Check

```bash
# Check specific aspect
python scripts/check_architecture.py --check-timeout src/bot.py
python scripts/check_architecture.py --check-except src/core/market_15m.py
python scripts/check_architecture.py --check-datetime src/core/polymarket.py

# Check everything
python scripts/check_architecture.py --all src/**/*.py
```

---

## 🚀 CI/CD Integration (Optional)

### GitHub Actions

Create `.github/workflows/architecture-check.yml`:

```yaml
name: Architecture Compliance

on: [push, pull_request]

jobs:
  check:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          pip install -r requirements-dev.txt

      - name: Run architecture checks
        run: |
          python scripts/check_architecture.py --all src/**/*.py

      - name: Run linting
        run: |
          flake8 src/
          black --check src/
          isort --check src/

      - name: Run type checking
        run: |
          mypy src/

      - name: Run security checks
        run: |
          bandit -r src/ -ll

      - name: Run tests
        run: |
          pytest tests/ --cov=src --cov-report=term-missing
```

---

## 📊 Monitoring Compliance

### Daily Check (Automated)

Set up a cron job or scheduled task:

```bash
# Linux/Mac - Add to crontab
0 9 * * * cd /path/to/Polymarket-bot && python scripts/check_architecture.py --all src/**/*.py

# Windows - Task Scheduler
# Create task that runs: python scripts/check_architecture.py --all src/**/*.py
```

### Metrics Dashboard (Optional)

Track compliance over time:

```bash
# Count violations by type
python scripts/check_architecture.py --all src/**/*.py 2>&1 | grep "violations" | tee compliance.log
```

---

## 🎓 Team Onboarding

### New Developer Setup

```bash
# 1. Clone repo
git clone https://github.com/your-org/Polymarket-bot.git
cd Polymarket-bot

# 2. Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 3. Install pre-commit hooks
pre-commit install

# 4. Read architecture docs
cat ARCHITECTURE.md
cat QUICK_REFERENCE.md

# 5. Generate first component
python scripts/generate_template.py --class MyFirstComponent

# 6. Check compliance
python scripts/check_architecture.py --all src/**/*.py

# 7. Run tests
pytest tests/ -v
```

### Training Checklist

New developers should:
- [ ] Read `ARCHITECTURE.md` (30 min)
- [ ] Read `QUICK_REFERENCE.md` (10 min)
- [ ] Install pre-commit hooks
- [ ] Generate a test component from template
- [ ] Run compliance checks
- [ ] Review 2-3 existing compliant files
- [ ] Complete first code review with senior dev

---

## 🔧 Troubleshooting

### Pre-Commit Hook Failing

```bash
# See what failed
git commit -v

# Run manually to see details
pre-commit run --all-files

# Skip hooks temporarily (not recommended)
git commit --no-verify
```

### Architecture Check False Positives

If a check incorrectly flags compliant code, you can:

1. **Add comment to ignore**:
   ```python
   # architecture-ignore: timeout (using custom wrapper)
   response = custom_request_wrapper(url)
   ```

2. **Update checker** in `scripts/check_architecture.py`

3. **Document exception** in `ARCHITECTURE.md`

### VSCode Not Formatting

1. Check Python interpreter is selected
2. Restart VSCode
3. Check `.vscode/settings.json` is present
4. Manually format: `Ctrl+Shift+P` → "Format Document"

---

## ✅ Verification

After setup, verify everything works:

```bash
# 1. Pre-commit installed
pre-commit --version

# 2. Hooks registered
cat .git/hooks/pre-commit | grep "pre-commit"

# 3. Tools available
black --version
flake8 --version
mypy --version

# 4. Architecture checker works
python scripts/check_architecture.py --all src/bot.py

# 5. Template generator works
python scripts/generate_template.py --class TestClass

# 6. Make a test commit
echo "# Test" >> test.txt
git add test.txt
git commit -m "Test commit"  # Should run hooks
git reset HEAD~1  # Undo test commit
rm test.txt
```

All checks should pass! ✅

---

## 📞 Support

- **Architecture Questions**: See `ARCHITECTURE.md`
- **Quick Help**: See `QUICK_REFERENCE.md`
- **Tool Issues**: Check this guide's Troubleshooting section
- **Code Review**: Use checklist in `ARCHITECTURE.md`

---

**Setup complete! Start writing compliant code.**
