import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[2]))

import pytest

from src.tools.sandbox.secure_executor import SecureToolSandbox, SecurityError


def test_sandbox_blocks_forbidden_pattern():
    sandbox = SecureToolSandbox()
    with pytest.raises(SecurityError):
        sandbox.execute_tool_sandboxed("rm", {"command": "rm -rf /"})


def test_sandbox_blocks_high_risk_tool():
    sandbox = SecureToolSandbox()
    with pytest.raises(SecurityError):
        sandbox.execute_tool_sandboxed("delete_resource", {"resource": "db"})
