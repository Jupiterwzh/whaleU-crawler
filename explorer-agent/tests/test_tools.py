from src.tools.registry import Tool, ToolRegistry


def _dummy_handler(path):
    return f"content of {path}"


def test_tool_to_openai_schema():
    t = Tool(name="read_file", description="读文件", parameters={"type": "object", "properties": {}}, handler=_dummy_handler)
    schema = t.to_openai_schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "read_file"
    assert schema["function"]["description"] == "读文件"


def test_registry_register_and_call():
    reg = ToolRegistry()
    reg.register(Tool("read_file", "读文件", {"type": "object", "properties": {}}, _dummy_handler))
    result = reg.call("read_file", {"path": "a.txt"})
    assert result == "content of a.txt"


def test_registry_call_unknown_raises():
    import pytest
    reg = ToolRegistry()
    with pytest.raises(KeyError):
        reg.call("nope", {})


import os
from src.tools.file_tools import make_file_tools

def test_read_file(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("hello")
    tools = make_file_tools(str(tmp_path))
    reg = ToolRegistry()
    for t in tools:
        reg.register(t)
    assert reg.call("read_file", {"path": str(f)}) == "hello"

def test_write_file(tmp_path):
    tools = make_file_tools(str(tmp_path))
    reg = ToolRegistry()
    for t in tools:
        reg.register(t)
    out = tmp_path / "out.txt"
    reg.call("write_file", {"path": str(out), "content": "data"})
    assert out.read_text() == "data"
