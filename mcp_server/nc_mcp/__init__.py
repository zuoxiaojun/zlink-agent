"""
NC (用友 NC Cloud) MCP 集成入口 (v1.5.0)

实际 NC 业务由外部 nc-mcp-server 包提供, 本目录只做:
- config: 把用户友好配置 (erp_clients.nc) 转换为 ORACLE_* 环境变量
- mcp_starter: 调 mcp_manager 启停 nc-mcp-server 进程
"""
