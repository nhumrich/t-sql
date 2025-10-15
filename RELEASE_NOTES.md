# Release Notes

## Version 2.2.0 (2025-01-XX)

### Fixed

**Parameter Name Sanitization for NAMED/PYFORMAT Styles**

Fixed a bug where complex Python expressions in t-strings would generate syntactically invalid SQL parameter names when using NAMED (`:name`) or PYFORMAT (`%(name)s`) parameter styles.

**Problem:**
- Complex expressions like `{data['key']}`, `{obj.attr}`, or `{func()}` would generate invalid SQL: `:data['key']`, `:obj.attr`, `:func()`
- These invalid parameter names caused database errors with SQLite, PostgreSQL, and other databases that use named parameters
- Example: `{a + b}` would generate `:a + b`, which databases would misinterpret as column references

**Solution:**
- Parameter names are now sanitized to valid SQL identifiers by replacing invalid characters with underscores
- Simple variable names are preserved for readability: `{user_input}` → `:user_input`
- Complex expressions are sanitized: `{data['key']}` → `:data__key__`, `{obj.name}` → `:obj_name`
- Collision detection ensures unique parameter names even with edge cases

**Breaking Change:**
- NAMED and PYFORMAT styles now correctly return `dict` parameters instead of `list`
- This aligns with SQL database driver expectations (SQLite, asyncpg, etc.)
- If you were manually handling parameters as lists, update to use dicts:
  ```python
  # Before (incorrect):
  sql, params = render(query, style=NAMED)
  # params was ['value1', 'value2']  # Wrong!

  # After (correct):
  sql, params = render(query, style=NAMED)
  # params is {'param1': 'value1', 'param2': 'value2'}
  ```

**Impact:**
- Queries using NAMED/PYFORMAT styles with complex expressions now work correctly
- All 247 existing tests continue to pass
- Added 10 new tests covering parameter name edge cases

This fix ensures t-sql generates valid SQL across all parameter styles and database drivers.
