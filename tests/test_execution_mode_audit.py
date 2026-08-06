"""Audit regression: write/state-mutating tools must be sequential.

Spec §4.5: 拿不准的工具一律标 sequential（并行是优化，串行是安全基线）。
"""

from __future__ import annotations

from agent.tools.registry import discover_tools, registry

SEQUENTIAL_TOOLS = {
    "execute_code",
    "patch",
    "write_file",
    "terminal",
    "process",
    "memory",
    "todo",
    "skill_install",
    "skill_activate",
    "skill_deactivate",
    "skill_export",
    "cronjob_create",
    "cronjob_update",
    "cronjob_delete",
    "cronjob_toggle",
    "cronjob_run",
    "mcp_add_server",
    "mcp_delete_server",
    "mcp_toggle_server",
    "mcp_reload_servers",
    "project_create",
    "project_switch",
    "ys_api",
    "nc_raw_sql",
    "close_terminal",
}

# 明确 parallel 的读/查询类工具抽查（防误标）
PARALLEL_SAMPLE = {
    "read_file",
    "ls",
    "glob",
    "search_files",
    "web_search",
    "web_extract",
    "session_search",
    "query_sale_orders",
    "nc_query",
    "tool_search",
    "tool_call",
    "clarify",
    "skill_list",
    "mcp_list_servers",
    "project_list",
    "cronjob_list",
}


def test_audited_sequential_tools_marked():
    discover_tools()
    for name in SEQUENTIAL_TOOLS:
        entry = registry.get_entry(name)
        assert entry is not None, f"{name} not registered"
        assert entry.execution_mode == "sequential", f"{name} must be sequential"


def test_parallel_tools_keep_default():
    discover_tools()
    for name in PARALLEL_SAMPLE:
        entry = registry.get_entry(name)
        assert entry is not None, f"{name} not registered"
        assert entry.execution_mode == "parallel", f"{name} must stay parallel"
