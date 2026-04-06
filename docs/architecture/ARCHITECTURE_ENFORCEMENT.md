# Architecture Enforcement System - Complete Guide

**How the Polymarket Bot ensures all code follows architecture standards**

---

## 📋 System Overview

The architecture enforcement system consists of **4 layers** that work together to ensure code quality:

```
Layer 1: Documentation  → What standards to follow
Layer 2: Tooling        → Code generators and templates
Layer 3: Automation     → Pre-commit hooks and checkers
Layer 4: Integration    → IDE support and CI/CD
```

---

## 🏗️ Complete File Structure

```
Polymarket-bot/
├── ARCHITECTURE.md                 # Complete architecture standards (MUST READ)
├── QUICK_REFERENCE.md              # One-page cheat sheet
├── SETUP.md                        # Installation and configuration guide
├── ARCHITECTURE_ENFORCEMENT.md     # This file - system overview
│
├── .pre-commit-config.yaml         # Pre-commit hook configuration
├── requirements-dev.txt            # Development dependencies
│
├── scripts/
│   ├── check_architecture.py       # Architecture compliance checker
│   └── generate_template.py        # Code template generator
│
├── .vscode/
│   ├── settings.json               # VSCode configuration (auto-format, linting)
│   └── polymarket.code-snippets    # Code snippets for common patterns
│
└── .github/
    └── workflows/
        └── architecture-check.yml  # CI/CD pipeline (optional)
```

---

## 📚 Layer 1: Documentation

### ARCHITECTURE.md (MANDATORY READING)
**Purpose**: Complete reference for all architecture standards

**Contents**:
- Core principles (fail-safe, thread-safe, resilient)
- Mandatory patterns with code examples
- Code guards (required for all API calls, threads, caches, etc.)
- Anti-patterns to avoid
- Module organization standards
- Class structure templates
- Testing standards
- Code review checklist
- Migration guide

**When to use**:
- Before writing any new code
- When reviewing code
- When unclear about best practices

---

### QUICK_REFERENCE.md (DAILY USE)
**Purpose**: One-page cheat sheet for quick lookups

**Contents**:
- Quick patterns (API calls, thread safety, caching, etc.)
- What NOT to do (common mistakes)
- Pre-commit checklist
- Tools commands
- Log format examples
- VSCode snippets

**When to use**:
- While actively coding
- Before committing
- Quick reference without reading full docs

---

### SETUP.md (ONE-TIME SETUP)
**Purpose**: Installation and configuration guide

**Contents**:
- Installation instructions
- VSCode integration
- Pre-commit hook setup
- Usage examples
- CI/CD integration
- Team onboarding
- Troubleshooting

**When to use**:
- Initial project setup
- Setting up new developer workstation
- Troubleshooting tool issues

---

## 🛠️ Layer 2: Tooling

### check_architecture.py
**Purpose**: Automated compliance checker

**Checks**:
1. ✅ **Timeout Check**: All `requests.get/post` have `timeout=` parameter
2. ✅ **Except Check**: No bare `except:` blocks
3. ✅ **Datetime Check**: All `datetime.now()` use `timezone.utc`
4. ✅ **Thread Safety Check**: Files using `Thread` also use `Lock`
5. ✅ **Cache Check**: Caches have `clear_cache()` methods

**Usage**:
```bash
# Check specific file
python scripts/check_architecture.py --all src/bot.py

# Check all Python files
python scripts/check_architecture.py --all src/**/*.py

# Check specific aspect
python scripts/check_architecture.py --check-timeout src/core/polymarket.py
```

**Output Example**:
```
================================================================================
ARCHITECTURE COMPLIANCE ERRORS
================================================================================

src/bot.py:150: requests call missing timeout parameter
  response = requests.get(url)
  Fix: Add timeout=10 parameter

src/core/market_15m.py:200: Bare except block (no exception type)
  except:
  Fix: Use 'except Exception as e:'

================================================================================
Total: 2 architecture violations found
See ARCHITECTURE.md for standards
================================================================================
```

---

### generate_template.py
**Purpose**: Generate compliant code from templates

**Templates Available**:
1. **Class Template**: Full class with retry logic, caching, thread safety
2. **Test Template**: Complete test suite with all test patterns

**Usage**:
```bash
# Generate new component class
python scripts/generate_template.py --class MarketAnalyzer > src/market_analyzer.py

# Generate test file
python scripts/generate_template.py --test MarketAnalyzer > tests/test_market_analyzer.py

# Preview template
python scripts/generate_template.py --class MyClass
```

**Template Features**:
- ✅ Includes `@retry_api_call` decorator
- ✅ Thread-safe with `Lock()`
- ✅ Cache with `clear_cache()` method
- ✅ Structured error responses
- ✅ UTC datetime
- ✅ Comprehensive docstrings
- ✅ All patterns from ARCHITECTURE.md

---

## ⚙️ Layer 3: Automation

### Pre-Commit Hooks
**Purpose**: Run checks automatically before each commit

**When Triggered**: Every `git commit` command

**Checks Run**:
1. **Black**: Auto-format code
2. **isort**: Sort imports
3. **Flake8**: Linting
4. **Mypy**: Type checking
5. **Bandit**: Security scanning
6. **Custom Architecture Checks**:
   - Timeout check
   - Bare except check
   - Datetime UTC check
   - Thread safety check
   - Cache expiration check

**Flow**:
```
git add .
git commit -m "Message"
  ↓
Pre-commit runs automatically
  ↓
All checks pass? → Commit succeeds
Any check fails? → Commit blocked, see errors
```

**Manual Run**:
```bash
# Run on all files
pre-commit run --all-files

# Run on specific files
pre-commit run --files src/bot.py

# Skip hooks (not recommended)
git commit --no-verify
```

---

## 💻 Layer 4: Integration

### VSCode Integration

**Auto-Format on Save**:
- Formats code with Black on every save
- Organizes imports with isort
- Shows linting errors inline

**Live Error Detection**:
- Flake8 highlights issues as you type
- Mypy shows type errors
- Bandit warns about security issues

**Code Snippets**:
Type prefix + Tab to insert:
- `poly-class` → Complete compliant class
- `poly-api` → API method with retry
- `poly-lock` → Thread-safe update
- `poly-response` → Structured response
- `poly-error` → Error handler
- `poly-datetime` → UTC datetime

**Setup**: See `SETUP.md` for VSCode configuration

---

### CI/CD Integration (Optional)

**GitHub Actions** (`.github/workflows/architecture-check.yml`):
- Runs on every push and pull request
- Checks architecture compliance
- Runs linting, type checking, security scans
- Runs test suite
- Fails PR if any check fails

**Prevents**:
- Non-compliant code from being merged
- Breaking changes without tests
- Security vulnerabilities

---

## 🔄 Development Workflow

### Standard Workflow

```bash
# 1. Start new feature
git checkout -b feature/my-feature

# 2. Generate template (if new file)
python scripts/generate_template.py --class MyComponent > src/my_component.py

# 3. Write code (VSCode auto-formats on save)
# ... edit files ...

# 4. Check compliance manually (optional but recommended)
python scripts/check_architecture.py --all src/my_component.py

# 5. Run tests
pytest tests/test_my_component.py -v

# 6. Commit (pre-commit hooks run automatically)
git add .
git commit -m "Add MyComponent with retry logic and thread safety"

# 7. If hooks fail, fix issues and commit again
# Hooks will re-run automatically

# 8. Push and create PR
git push origin feature/my-feature
```

---

### Quick Fix Workflow

```bash
# 1. Make small change
# ... edit file ...

# 2. Quick check
python scripts/check_architecture.py --all src/changed_file.py

# 3. Commit (hooks auto-run)
git commit -am "Quick fix"
```

---

## 📊 Compliance Monitoring

### Real-Time Metrics

Track compliance over time:

```bash
# Count violations
python scripts/check_architecture.py --all src/**/*.py 2>&1 | \
  grep "violations" | \
  tee -a compliance_log.txt

# Track over time
echo "$(date),$(python scripts/check_architecture.py --all src/**/*.py 2>&1 | grep 'violations' | awk '{print $2}')" >> metrics.csv
```

### Weekly Dashboard

```bash
# violations_by_type.sh
echo "=== Architecture Violations by Type ==="
python scripts/check_architecture.py --check-timeout src/**/*.py 2>&1 | grep "Total:"
python scripts/check_architecture.py --check-except src/**/*.py 2>&1 | grep "Total:"
python scripts/check_architecture.py --check-datetime src/**/*.py 2>&1 | grep "Total:"
python scripts/check_architecture.py --check-threads src/**/*.py 2>&1 | grep "Total:"
python scripts/check_architecture.py --check-cache src/**/*.py 2>&1 | grep "Total:"
```

---

## 🎓 Team Standards

### For All Developers

**MUST DO**:
1. ✅ Read `ARCHITECTURE.md` before first contribution
2. ✅ Install pre-commit hooks (`pre-commit install`)
3. ✅ Use templates for new components
4. ✅ Check compliance before committing
5. ✅ Keep `QUICK_REFERENCE.md` handy

**MUST NOT DO**:
1. ❌ Commit with `--no-verify` (skips hooks)
2. ❌ Ignore architecture checker warnings
3. ❌ Copy non-compliant code patterns
4. ❌ Skip code review checklist

---

### For Code Reviewers

**Check These Before Approving PR**:

```markdown
## Architecture Compliance Checklist

- [ ] All API calls have `timeout=10`
- [ ] No bare `except:` blocks
- [ ] All `datetime.now()` use `timezone.utc`
- [ ] Shared mutable state protected with `Lock()`
- [ ] Caches have `clear_cache()` method
- [ ] Error messages include diagnostic context
- [ ] Tests pass
- [ ] Pre-commit hooks pass
- [ ] Follows patterns from ARCHITECTURE.md
```

---

### For Project Leads

**Maintain Standards**:
1. Update `ARCHITECTURE.md` when patterns change
2. Add new checks to `check_architecture.py` as needed
3. Review and update templates quarterly
4. Monitor compliance metrics weekly
5. Train new developers on standards

---

## 🆘 Troubleshooting

### "Pre-commit hook failing"

```bash
# See what failed
pre-commit run --all-files

# Fix issues, then commit again
git commit -m "Same message"
```

### "Architecture checker has false positive"

Options:
1. Add exemption comment in code
2. Update checker script if wrong
3. Document exception in ARCHITECTURE.md

### "Template doesn't match my needs"

1. Generate base template
2. Customize as needed
3. Keep architectural patterns intact
4. Consider contributing improved template

---

## 📈 Success Metrics

Track these to measure effectiveness:

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Pre-commit hook pass rate | >90% | Count git commits vs. hook failures |
| Architecture violations | <5 per file | Run `check_architecture.py --all` |
| Code review cycles | <2 per PR | Track PR comments on architecture |
| Test coverage | >80% | `pytest --cov` |
| Security issues | 0 | `bandit -r src/` |

---

## 🔮 Future Enhancements

**Planned**:
- [ ] Auto-fix mode for common violations
- [ ] Real-time dashboard for compliance metrics
- [ ] AI-powered code review assistant
- [ ] More sophisticated thread safety detection
- [ ] Performance regression testing
- [ ] Automated architecture documentation updates

**Suggestions Welcome**: Add to `ARCHITECTURE.md` or discuss in team meetings

---

## 📞 Getting Help

| Question Type | Resource |
|---------------|----------|
| "How do I...?" | `QUICK_REFERENCE.md` |
| "Why this pattern?" | `ARCHITECTURE.md` |
| "How to install?" | `SETUP.md` |
| "What's the big picture?" | This file |
| "Tool not working" | `SETUP.md` → Troubleshooting |
| "Found a bug" | Create GitHub issue |

---

## ✅ Verification

System is working correctly when:

1. ✅ `pre-commit run --all-files` passes on compliant code
2. ✅ `python scripts/check_architecture.py --all src/**/*.py` passes
3. ✅ VSCode auto-formats on save
4. ✅ Templates generate without errors
5. ✅ Git commits trigger pre-commit hooks
6. ✅ Tests pass: `pytest tests/ -v`

---

## 🎯 Quick Start

**I'm a new developer, where do I start?**

1. **Day 1**: Read `ARCHITECTURE.md` (30 min) + `QUICK_REFERENCE.md` (10 min)
2. **Day 1**: Run setup from `SETUP.md` (15 min)
3. **Day 2**: Generate a test component, modify it, run checks
4. **Day 3**: Start contributing with guidance from senior dev
5. **Ongoing**: Keep `QUICK_REFERENCE.md` open while coding

**I'm making a quick fix, what do I need?**

1. Edit file
2. Run: `python scripts/check_architecture.py --all your_file.py`
3. Commit (hooks auto-run)
4. Done!

**I'm creating a new component, what do I need?**

1. Generate template: `python scripts/generate_template.py --class MyClass`
2. Customize generated code
3. Generate tests: `python scripts/generate_template.py --test MyClass`
4. Check compliance: `python scripts/check_architecture.py --all src/my_class.py`
5. Commit with hooks

---

**This system ensures consistent, high-quality, production-ready code across the entire Polymarket Bot project.**

All code changes MUST follow these standards. No exceptions without documented justification.
