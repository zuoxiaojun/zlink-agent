#!/usr/bin/env python3
"""解析 NC65 数据字典 CHM → nc_dictionary.json

用法:
    .venv/bin/python scripts/parse_nc_dict_chm.py ~/Desktop/65数据字典.chm
    .venv/bin/python scripts/parse_nc_dict_chm.py /tmp/nc_dict --modules so,pu,ic -o out.json

输出路径:
    默认写到 DATA_DIR/nc_dictionary.json（本机覆盖层，优先生效）；
    要更新随包分发的字典用 -o agent/tools/nc_dictionary.json 并提交 git。

输出结构:
    {
      "modules": {"so": "销售管理", ...},
      "tables":  {"SO_SALEORDER": {"name": "销售订单主实体", "module": "so",
                                   "fields": {"VBILLCODE": {"name": "单据号",
                                   "type": "varchar(30)", "enum": "...", "ref": "..."}}}}
    }
"""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path

DEFAULT_MODULES = "so,pu,ic,gl,arap,cmp"


def extract_chm(chm_path: Path, dest: Path) -> None:
    subprocess.run(["7z", "x", "-y", str(chm_path)], cwd=dest, check=True, capture_output=True)


def parse_toc(hhc_path: Path) -> tuple[dict[str, str], dict[str, list[tuple[str, str, str]]]]:
    """解析 000_toc.hhc → (模块码→中文名, 模块码→[(表名, 中文名, html文件)])"""
    raw = hhc_path.read_bytes().decode("gb18030", errors="replace")
    depth = 0
    tokens: list[tuple[int, str, str | None]] = []
    for tok in re.finditer(r"<ul>|</ul>|name=\"Name\" value=\"([^\"]*)\"|name=\"Local\" value=\"([^\"]*)\"", raw, re.I):
        s = tok.group(0).lower()
        if s == "<ul>":
            depth += 1
        elif s == "</ul>":
            depth -= 1
        elif tok.group(1) is not None:
            tokens.append((depth, html.unescape(tok.group(1)), None))
        elif tokens:
            d0, n0, _ = tokens[-1]
            tokens[-1] = (d0, n0, tok.group(2))

    module_names: dict[str, str] = {}
    module_tables: dict[str, list[tuple[str, str, str]]] = {}
    cur: str | None = None
    for d, name, local in tokens:
        if d == 1 and local is None:
            parts = name.split(None, 1)
            cur = parts[0]
            module_names[cur] = parts[1] if len(parts) > 1 else cur
            module_tables.setdefault(cur, [])
        elif d == 2 and local and cur:
            parts = name.split(None, 1)
            table = parts[0].upper()
            cn = parts[1] if len(parts) > 1 else ""
            module_tables[cur].append((table, cn, local))
    return module_names, module_tables


class _TableRowParser(HTMLParser):
    """提取 HTML 页面里所有表格行（cell 文本列表）。"""

    def __init__(self):
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._in_cell = False
        self._cell: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._in_cell = True
            self._cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._in_cell:
            self._in_cell = False
            if self._row is not None:
                self._row.append(re.sub(r"\s+", " ", "".join(self._cell)).strip())
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._in_cell:
            self._cell.append(data)


_COL_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")


def parse_fields(html_path: Path) -> dict[str, dict]:
    """解析单张表的字段表 → {列名: {name, type?, ref?, enum?}}"""
    raw = html_path.read_bytes().decode("gb18030", errors="replace")
    p = _TableRowParser()
    p.feed(raw)

    header = None
    header_idx = 0
    for i, row in enumerate(p.rows):
        if "字段编码" in row and "名称" in row:
            header, header_idx = row, i
            break
    if header is None:
        return {}

    def col(*names: str) -> int | None:
        for n in names:
            if n in header:
                return header.index(n)
        return None

    i_code, i_name, i_type = col("字段编码"), col("名称"), col("字段类型")
    i_ref, i_enum = col("引用模型"), col("枚举")
    if i_code is None or i_name is None:
        return {}

    fields: dict[str, dict] = {}
    for row in p.rows[header_idx + 1 :]:
        if len(row) <= max(i_code, i_name):
            continue
        code = row[i_code].upper()
        if not _COL_RE.match(code):
            continue
        f: dict[str, str] = {"name": row[i_name]}
        for idx, key in ((i_type, "type"), (i_ref, "ref"), (i_enum, "enum")):
            if idx is not None and idx < len(row) and row[idx]:
                f[key] = row[idx]
        fields[code] = f
    return fields


def main() -> int:
    ap = argparse.ArgumentParser(description="解析 NC65 数据字典 CHM")
    ap.add_argument("source", help="CHM 文件路径或已解包的目录")
    ap.add_argument("--modules", default=DEFAULT_MODULES, help=f"逗号分隔模块码（默认 {DEFAULT_MODULES}）")
    ap.add_argument("--extra-tables", default="", help="跨模块补充的表名，逗号分隔（如 bd_account,bd_accasoa）")
    ap.add_argument("-o", "--output", help="输出 JSON 路径（默认 DATA_DIR/nc_dictionary.json）")
    args = ap.parse_args()

    src = Path(args.source).expanduser()
    if src.is_file() and src.suffix.lower() == ".chm":
        tmp = tempfile.TemporaryDirectory(prefix="nc_dict_")
        extract_chm(src, Path(tmp.name))
        workdir = Path(tmp.name)
    elif src.is_dir():
        tmp = None
        workdir = src
    else:
        print(f"找不到: {src}", file=sys.stderr)
        return 1

    wanted = [m.strip() for m in args.modules.split(",") if m.strip()]
    extra = {t.strip().upper() for t in args.extra_tables.split(",") if t.strip()}
    module_names, module_tables = parse_toc(workdir / "000_toc.hhc")

    for mod in wanted:
        if mod not in module_tables:
            print(f"⚠️  模块不存在: {mod}", file=sys.stderr)

    # 收集候选：同表可能多个条目（权限实体/视图等），取字段最丰富的页面
    candidates: dict[str, list[tuple[str, str, str]]] = {}
    for mod, entries in module_tables.items():
        for table, cn, local in entries:
            if mod in wanted or table in extra:
                candidates.setdefault(table, []).append((cn, local, mod))

    out_modules: dict[str, str] = {}
    out_tables: dict[str, dict] = {}
    dup_resolved = 0
    for table, cands in candidates.items():
        best: tuple[str, str, dict] | None = None
        for cn, local, mod in cands:
            page = workdir / local
            if not page.exists():
                continue
            fields = parse_fields(page)
            if best is None or len(fields) > len(best[2]):
                best = (cn, mod, fields)
        if best is None:
            continue
        dup_resolved += len(cands) - 1
        cn, mod, fields = best
        out_tables[table] = {"name": cn, "module": mod, "fields": fields}
        if mod in wanted or mod in {c[2] for c in cands}:
            out_modules.setdefault(mod, module_names.get(mod, mod))

    if args.output:
        out_path = Path(args.output).expanduser()
    else:
        try:
            from agent.utils import DATA_DIR

            out_path = DATA_DIR / "nc_dictionary.json"
        except Exception:
            out_path = Path.home() / ".zlink-agent" / "data" / "nc_dictionary.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps({"modules": out_modules, "tables": out_tables}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )

    total_fields = sum(len(t["fields"]) for t in out_tables.values())
    print(f"✅ {len(out_modules)} 模块 / {len(out_tables)} 表 / {total_fields} 字段 -> {out_path}")
    if dup_resolved:
        print(f"   （{dup_resolved} 个同名条目取字段最丰富的页面）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
