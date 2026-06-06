# Python Version Compatibility

## Supported Versions
- **Python 3.8+** (Full support)
- **Python 3.9, 3.10, 3.11, 3.12** (Tested)

## Type Annotation Standards
This project uses Python 3.8 compatible type hints:

✅ **DO USE:**
```python
from typing import Optional, List, Dict, Union

def function(param: Optional[str] = None) -> List[int]:
    pass
```

❌ **DON'T USE (Python 3.10+ only):**
```python
def function(param: str | None = None) -> list[int]:
    pass
```

## Recent Fixes (2026-06-06)
- Fixed `list[int]` → `List[int]` in config.py
- Fixed `str | None` → `Optional[str]` throughout codebase
- Fixed `DatabaseManager | None` → `Optional[DatabaseManager]`
- Removed duplicate dependencies in requirements.txt

## CI/CD Testing
All code is validated against Python 3.8+ using mypy and pylint.
See `run_tests.sh` for testing procedures.
