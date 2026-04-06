# 🏛️ Architecture Standards System

**Professional-grade architecture enforcement for Polymarket Bot**

---

## 🎯 What This System Does

Makes **architectural excellence mandatory** through:
- 📖 **Comprehensive documentation** of all standards
- 🤖 **Automated compliance checking** before every commit
- 🛠️ **Code generation** from compliant templates
- 💻 **IDE integration** for real-time feedback
- ✅ **CI/CD enforcement** to prevent non-compliant merges

**Result**: All code automatically follows the same high standards, forever.

---

## 📁 What Was Created

### Core Documentation (START HERE)

| File | Purpose | Read Time | When to Use |
|------|---------|-----------|-------------|
| `ARCHITECTURE.md` | Complete standards reference | 30 min | Before writing any code |
| `QUICK_REFERENCE.md` | One-page cheat sheet | 5 min | While coding (keep open) |
| `SETUP.md` | Installation & configuration | 15 min | One-time setup |
| `ARCHITECTURE_ENFORCEMENT.md` | System overview | 10 min | Understanding the system |

### Automation Tools

| File | Purpose |
|------|---------|
| `.pre-commit-config.yaml` | Pre-commit hooks configuration |
| `scripts/check_architecture.py` | Compliance checker |
| `scripts/generate_template.py` | Code template generator |
| `requirements-dev.txt` | Development dependencies |

### IDE Integration

| File | Purpose |
|------|---------|
| `.vscode/settings.json` | Auto-format, linting |
| `.vscode/polymarket.code-snippets` | Code snippets |

---

## ⚡ Quick Start (5 Minutes)

### 1. Install Tools

```bash
cd C:\Users\lhsim\OneDrive\Documentos\Polymarket-bot

# Install development dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

### 2. Verify Installation

```bash
# Test architecture checker
python scripts/check_architecture.py --all src/bot.py

# Test template generator
python scripts/generate_template.py --class TestClass

# Test pre-commit hooks
pre-commit run --all-files
```

### 3. Read the Docs

```bash
# Essential reading (10 minutes)
cat QUICK_REFERENCE.md

# Deep dive (30 minutes when you have time)
cat ARCHITECTURE.md
```

---

## 🚀 Usage

### Daily Workflow

```bash
# 1. Write code (VSCode auto-formats on save)
# 2. Check compliance
python scripts/check_architecture.py --all src/my_file.py

# 3. Commit (hooks run automatically)
git commit -m "Your message"

# If hooks fail, fix issues and commit again
```

### Creating New Components

```bash
# Generate compliant template
python scripts/generate_template.py --class MyComponent > src/my_component.py

# Generate tests
python scripts/generate_template.py --test MyComponent > tests/test_my_component.py

# Edit as needed, keeping architecture patterns
```

### Before Each Commit

**Pre-Commit Checklist** (from `QUICK_REFERENCE.md`):
- [ ] API calls have `timeout=10`
- [ ] No `except:` without exception type
- [ ] All `datetime.now()` use `timezone.utc`
- [ ] Shared state protected with `Lock()`
- [ ] Caches have `clear_cache()` method
- [ ] Errors have diagnostic context
- [ ] Tests pass

---

## 🏗️ Architecture Standards Summary

### Core Principles (from `ARCHITECTURE.md`)

1. **Fail-Safe, Not Fail-Silent**
   - Never use bare `except: pass`
   - Always log errors with context
   - Return structured error responses

2. **Thread-Safe by Default**
   - All shared mutable state protected with `Lock()`
   - Document thread safety in docstrings

3. **Resilient API Calls**
   - All external APIs use `timeout=10`
   - All network calls use `@retry_api_call` decorator
   - Exponential backoff for transient failures

4. **Cache Expiration**
   - All caches have `clear_cache()` method
   - Document cache lifetime
   - Clear caches when data becomes stale

5. **UTC Always**
   - All datetime operations use `datetime.now(timezone.utc)`
   - Never mix local and UTC times

6. **Observability First**
   - Log all state transitions
   - Include context in error messages
   - Use structured logging format

---

## 📋 What Each Document Contains

### ARCHITECTURE.md (MANDATORY)
✅ Complete reference for all standards
- Core principles
- Mandatory patterns with examples
- Anti-patterns to avoid
- Code review checklist
- Testing standards
- Migration guide

### QUICK_REFERENCE.md (DAILY USE)
✅ One-page cheat sheet
- Quick patterns
- What NOT to do
- Pre-commit checklist
- Common commands
- VSCode snippets

### SETUP.md (ONE-TIME)
✅ Installation guide
- Tool installation
- VSCode integration
- Pre-commit setup
- CI/CD integration
- Troubleshooting

### ARCHITECTURE_ENFORCEMENT.md (OVERVIEW)
✅ How the system works
- 4-layer architecture
- Tool documentation
- Development workflow
- Compliance monitoring
- Team standards

---

## 🛠️ Tools Reference

### Architecture Compliance Checker

**Check everything**:
```bash
python scripts/check_architecture.py --all src/**/*.py
```

**Check specific aspects**:
```bash
python scripts/check_architecture.py --check-timeout src/bot.py
python scripts/check_architecture.py --check-except src/core/market_15m.py
python scripts/check_architecture.py --check-datetime src/core/polymarket.py
python scripts/check_architecture.py --check-threads src/bot.py
python scripts/check_architecture.py --check-cache src/core/market_15m.py
```

### Template Generator

**Generate new component**:
```bash
python scripts/generate_template.py --class ComponentName > src/component_name.py
```

**Generate test file**:
```bash
python scripts/generate_template.py --test ComponentName > tests/test_component_name.py
```

### Pre-Commit Hooks

**Run manually on all files**:
```bash
pre-commit run --all-files
```

**Run on specific files**:
```bash
pre-commit run --files src/bot.py src/core/polymarket.py
```

**Update hooks**:
```bash
pre-commit autoupdate
```

---

## 💡 Common Patterns

### API Call with Retry
```python
@retry_api_call(max_retries=3)
def _fetch_data(self, url):
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()
```

### Thread-Safe Update
```python
data_lock = Lock()

def update_data(key, value):
    with data_lock:
        self.data[key] = value
```

### Cache with Expiration
```python
def clear_cache(self):
    self.cache.clear()
    print("  [CACHE] Cache cleared")
```

### Structured Response
```python
return {
    'success': True,
    'data': result,
    'error': None
}
```

### UTC Datetime
```python
from datetime import datetime, timezone
now = datetime.now(timezone.utc)
```

**More patterns**: See `QUICK_REFERENCE.md`

---

## ✅ Enforcement Mechanisms

### Automatic (No Manual Intervention)

1. **Pre-commit hooks** run on every `git commit`
   - Formats code
   - Sorts imports
   - Checks compliance
   - Runs linters
   - Type checking
   - Security scans

2. **VSCode auto-format** on every save
   - Black formatting
   - Import organization
   - Inline error detection

### Semi-Automatic (Developer Initiated)

1. **Manual compliance check**:
   ```bash
   python scripts/check_architecture.py --all src/**/*.py
   ```

2. **Test suite**:
   ```bash
   pytest tests/ -v --cov=src
   ```

### Manual (Code Review)

1. **Code review checklist** from `ARCHITECTURE.md`
2. **Team member verification**
3. **Documentation review**

---

## 📊 Success Metrics

Track these to measure system effectiveness:

| Metric | Target | Command |
|--------|--------|---------|
| Architecture violations | 0 | `python scripts/check_architecture.py --all src/**/*.py` |
| Test coverage | >80% | `pytest --cov=src --cov-report=term-missing` |
| Pre-commit pass rate | >90% | Count commits vs. failures |
| Security issues | 0 | `bandit -r src/ -ll` |

---

## 🎓 Training Path

### For New Developers

**Day 1** (1 hour):
1. Read this README (10 min)
2. Read `QUICK_REFERENCE.md` (10 min)
3. Run setup from `SETUP.md` (15 min)
4. Read `ARCHITECTURE.md` sections 1-3 (25 min)

**Day 2** (1 hour):
1. Generate test component
2. Modify it following patterns
3. Run compliance checks
4. Make test commit

**Ongoing**:
- Keep `QUICK_REFERENCE.md` open while coding
- Reference `ARCHITECTURE.md` when unsure
- Use templates for new components

### For Experienced Developers

1. Skim `ARCHITECTURE.md` for patterns (15 min)
2. Review `QUICK_REFERENCE.md` (5 min)
3. Install tools from `SETUP.md` (10 min)
4. Start coding with standards

---

## 🆘 Getting Help

| Question | Document |
|----------|----------|
| "How do I install tools?" | `SETUP.md` |
| "What are the standards?" | `ARCHITECTURE.md` |
| "Quick pattern lookup?" | `QUICK_REFERENCE.md` |
| "How does the system work?" | `ARCHITECTURE_ENFORCEMENT.md` |
| "Tool not working?" | `SETUP.md` → Troubleshooting |
| "General overview?" | This file |

---

## 🔄 System Updates

### When to Update Standards

- New architectural pattern discovered
- Common bug pattern identified
- Team consensus on improvement
- New tool or framework adopted

### How to Update

1. Update `ARCHITECTURE.md` with new pattern
2. Add check to `scripts/check_architecture.py` if needed
3. Update templates in `scripts/generate_template.py`
4. Update `QUICK_REFERENCE.md` with quick example
5. Notify team of changes

---

## 🎯 Next Steps

### Right Now (5 minutes)
```bash
# 1. Install tools
pip install -r requirements-dev.txt
pre-commit install

# 2. Verify
python scripts/check_architecture.py --all src/bot.py
```

### Today (30 minutes)
- Read `QUICK_REFERENCE.md` thoroughly
- Skim `ARCHITECTURE.md` core principles

### This Week (2 hours)
- Read full `ARCHITECTURE.md`
- Generate a test component from template
- Make a compliant code change with all checks

### Ongoing
- Use templates for new components
- Run checks before committing
- Keep standards top of mind

---

## ✨ Benefits You'll See

**Immediate**:
- ✅ Automated code formatting
- ✅ Catch bugs before commit
- ✅ Faster code reviews
- ✅ Consistent code style

**Short-term** (1-2 weeks):
- ✅ Write compliant code naturally
- ✅ Fewer bugs in production
- ✅ Better error messages
- ✅ Easier debugging

**Long-term** (1-3 months):
- ✅ Higher code quality across project
- ✅ Faster onboarding for new developers
- ✅ Reduced technical debt
- ✅ Professional-grade codebase

---

## 📞 Support

- **Quick Questions**: See `QUICK_REFERENCE.md`
- **Detailed Info**: See `ARCHITECTURE.md`
- **Setup Issues**: See `SETUP.md` troubleshooting
- **System Overview**: See `ARCHITECTURE_ENFORCEMENT.md`
- **Bugs/Improvements**: Create GitHub issue

---

## ⭐ Key Takeaways

1. **All code MUST follow standards** - No exceptions without justification
2. **Tools automate compliance** - Pre-commit hooks catch issues automatically
3. **Templates provide starting point** - Use them for new components
4. **Documentation is comprehensive** - Everything is documented
5. **System is self-enforcing** - Can't commit non-compliant code

---

**Welcome to professional-grade development. Let's build something amazing!** 🚀
