import asyncio
import json
import pytest
from MCP_Server.tools._base import _tool_handler, tool_success, tool_error, _m4l_result


class TestToolHandler:
    @pytest.mark.asyncio
    async def test_basic_success(self):
        @_tool_handler("test operation")
        def my_tool():
            return "success"

        result = await my_tool()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_value_error_caught(self):
        @_tool_handler("test operation")
        def my_tool():
            raise ValueError("bad input")

        result = await my_tool()
        assert "Invalid input" in result
        assert "bad input" in result

    @pytest.mark.asyncio
    async def test_connection_error_caught(self):
        @_tool_handler("test operation")
        def my_tool():
            raise ConnectionError("no connection")

        result = await my_tool()
        assert "M4L bridge not available" in result

    @pytest.mark.asyncio
    async def test_generic_exception_caught(self):
        @_tool_handler("doing stuff")
        def my_tool():
            raise RuntimeError("something broke")

        result = await my_tool()
        assert "Error doing stuff" in result

    @pytest.mark.asyncio
    async def test_with_args(self):
        @_tool_handler("test")
        def my_tool(a, b):
            return f"{a}+{b}"

        result = await my_tool(1, 2)
        assert result == "1+2"


class TestToolSuccess:
    def test_basic(self):
        result = json.loads(tool_success("Done"))
        assert result["status"] == "ok"
        assert result["message"] == "Done"

    def test_with_data(self):
        result = json.loads(tool_success("Done", {"count": 5}))
        assert result["data"]["count"] == 5


class TestToolError:
    def test_basic(self):
        result = json.loads(tool_error("Failed"))
        assert result["status"] == "error"
        assert result["message"] == "Failed"


class TestM4lResult:
    def test_success(self):
        result = _m4l_result({"status": "success", "result": {"value": 42}})
        assert result["value"] == 42

    def test_error_raises(self):
        with pytest.raises(Exception, match="M4L bridge error"):
            _m4l_result({"status": "error", "message": "device not found"})
