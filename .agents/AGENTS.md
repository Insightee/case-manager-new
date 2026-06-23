## Learned User Preferences & Token Optimization Rules

### Token-Efficient Testing Doctrine
To minimize token consumption and reduce latency, always prioritize targeted test execution over running the full test suite:

1. **Targeted Test Execution**:
   - Run only the specific test files or individual test functions affected by the changes.
   - Use the direct file path (e.g., `pytest app/tests/test_file.py`) or the `-k` filter (e.g., `pytest -k "test_func_name"`) to run a subset of tests.
   - Avoid executing the entire test suite unless:
     - Explicitly requested by the user.
     - Preparing a final release/pre-push check where full validation is critical.

2. **Output Minimization**:
   - When running test commands, use flags that reduce output size (such as `-q` or `--tb=short`) to avoid cluttering the agent's context window with large logs.

### Tool & Customization Optimization
To prevent bloating the context window and save tokens, optimize the loadout of external tools and capabilities:

1. **Minimize MCP & Skill Usage**:
   - Do not load, register, or execute custom skills or MCP servers that are not directly relevant to the current task.
   - Use only the skills and MCP tools that are explicitly called upon or required to resolve the specific task at hand.
