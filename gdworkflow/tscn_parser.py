"""Parse and write Godot 4.x .tscn scene files.

The .tscn format is an INI-like structured text format with sections:
- [gd_scene ...] header
- [ext_resource ...] external resource references
- [sub_resource ...] internal resource definitions (with properties)
- [node ...] scene tree nodes (with properties)
- [connection ...] signal connections

Each section starts with a bracketed header on its own line.
Properties follow as key = value pairs (one per line) until the next section.
Sections are separated by blank lines.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ExtResource:
    id: str
    type: str
    uid: str
    path: str

    def to_line(self) -> str:
        return f'[ext_resource type="{self.type}" uid="{self.uid}" path="{self.path}" id="{self.id}"]'


@dataclass
class SubResource:
    id: str
    type: str
    properties: list[str] = field(default_factory=list)

    def to_lines(self) -> list[str]:
        lines = [f'[sub_resource type="{self.type}" id="{self.id}"]']
        lines.extend(self.properties)
        return lines


@dataclass
class NodeEntry:
    name: str
    properties: list[str] = field(default_factory=list)
    parent: Optional[str] = None
    node_type: Optional[str] = None
    instance: Optional[str] = None
    unique_id: Optional[int] = None

    def header_line(self) -> str:
        parts = [f'name="{self.name}"']
        if self.parent is not None:
            parts.append(f'parent="{self.parent}"')
        if self.node_type is not None:
            parts.append(f'type="{self.node_type}"')
        if self.instance is not None:
            parts.append(f'instance={self.instance}')
        if self.unique_id is not None:
            parts.append(f'unique_id={self.unique_id}')
        return f'[node {" ".join(parts)}]'

    def to_lines(self) -> list[str]:
        lines = [self.header_line()]
        lines.extend(self.properties)
        return lines


@dataclass
class Connection:
    signal: str
    from_path: str
    to_path: str
    method: str
    flags: Optional[int] = None

    def to_line(self) -> str:
        parts = [
            f'signal="{self.signal}"',
            f'from="{self.from_path}"',
            f'to="{self.to_path}"',
            f'method="{self.method}"',
        ]
        if self.flags is not None:
            parts.append(f'flags={self.flags}')
        return f'[connection {" ".join(parts)}]'


@dataclass
class TscnFile:
    header: str = ""
    ext_resources: list[ExtResource] = field(default_factory=list)
    sub_resources: list[SubResource] = field(default_factory=list)
    nodes: list[NodeEntry] = field(default_factory=list)
    connections: list[Connection] = field(default_factory=list)

    def max_ext_resource_id(self) -> int:
        max_id = 0
        for r in self.ext_resources:
            try:
                val = int(r.id.split("_")[0]) if "_" in r.id else int(r.id)
                max_id = max(max_id, val)
            except ValueError:
                continue
        return max_id

    def generate_ext_resource_id(self, prefix: str = "") -> str:
        max_id = self.max_ext_resource_id()
        new_num = max_id + 1
        return f"{new_num}{prefix}" if prefix else str(new_num)

    def add_ext_resource(self, type_: str, uid: str, path: str, id_: Optional[str] = None) -> str:
        if id_ is None:
            id_ = self.generate_ext_resource_id()
        er = ExtResource(id=id_, type=type_, uid=uid, path=path)
        self.ext_resources.append(er)
        return id_

    def add_node_instance(self, name: str, parent: str, instance_id: str,
                          properties: Optional[list[str]] = None) -> NodeEntry:
        node = NodeEntry(
            name=name,
            parent=parent,
            instance=f'ExtResource("{instance_id}")',
            properties=properties or [],
        )
        self.nodes.append(node)
        return node

    def add_connection(self, signal: str, from_path: str, to_path: str,
                       method: str, flags: Optional[int] = None) -> Connection:
        conn = Connection(
            signal=signal,
            from_path=from_path,
            to_path=to_path,
            method=method,
            flags=flags,
        )
        self.connections.append(conn)
        return conn

    def to_string(self) -> str:
        lines = []
        if self.header:
            lines.append(self.header)
            lines.append("")

        for er in self.ext_resources:
            lines.append(er.to_line())
            lines.append("")

        for sr in self.sub_resources:
            sr_lines = sr.to_lines()
            lines.extend(sr_lines)
            lines.append("")

        for node in self.nodes:
            node_lines = node.to_lines()
            lines.extend(node_lines)
            lines.append("")

        for conn in self.connections:
            lines.append(conn.to_line())
            lines.append("")

        return "\n".join(lines)

    def write(self, path: Path) -> None:
        content = self.to_string()
        path.write_text(content, encoding="utf-8")


_HEADER_RE = re.compile(r"^\[gd_scene\s.*\]$", re.DOTALL)
_EXT_RESOURCE_RE = re.compile(
    r'^\[ext_resource\s+type="([^"]+)"\s+uid="([^"]+)"\s+path="([^"]+)"\s+id="([^"]+)"\]$'
)
_ALT_EXT_RESOURCE_RE = re.compile(
    r'^\[ext_resource\s+.*id="([^"]+)".*\]$'
)
_SUB_RESOURCE_RE = re.compile(r'^\[sub_resource\s+type="([^"]+)"\s+id="([^"]+)"\]$')
_NODE_RE = re.compile(r'^\[node\s+(.*)\]$')
_CONNECTION_RE = re.compile(
    r'^\[connection\s+signal="([^"]+)"\s+from="([^"]+)"\s+to="([^"]+)"\s+method="([^"]+)"'
)
_CONNECTION_FLAGS_RE = re.compile(r"flags=(\d+)")


def parse_tscn(path: Path) -> TscnFile:
    content = path.read_text(encoding="utf-8")
    return parse_tscn_string(content)


def parse_tscn_string(content: str) -> TscnFile:
    tscn = TscnFile()
    lines = content.split("\n")

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if not line or line.startswith(";"):
            i += 1
            continue

        if line.startswith("[gd_scene"):
            tscn.header = _parse_header_with_properties(lines, i)
            i = _skip_block(lines, i)
            continue

        m = _EXT_RESOURCE_RE.match(line)
        if m:
            er = ExtResource(
                type=m.group(1),
                uid=m.group(2),
                path=m.group(3),
                id=m.group(4),
            )
            tscn.ext_resources.append(er)
            i += 1
            continue

        if line.startswith("[ext_resource"):
            am = _ALT_EXT_RESOURCE_RE.match(line)
            if am:
                id_ = am.group(1)
                props = _extract_properties(line)
                er = ExtResource(
                    id=id_,
                    type=props.get("type", ""),
                    uid=props.get("uid", ""),
                    path=props.get("path", ""),
                )
                tscn.ext_resources.append(er)
            i += 1
            continue

        m = _SUB_RESOURCE_RE.match(line)
        if m:
            sr = SubResource(type=m.group(1), id=m.group(2))
            i += 1
            while i < len(lines):
                sub_line = lines[i].strip()
                if not sub_line or sub_line.startswith("[") or sub_line.startswith(";"):
                    break
                sr.properties.append(lines[i].rstrip())
                i += 1
            tscn.sub_resources.append(sr)
            continue

        m = _NODE_RE.match(line)
        if m:
            node = _parse_node_header_line(line)
            i += 1
            while i < len(lines):
                sub_line = lines[i].strip()
                if not sub_line or sub_line.startswith("[") or sub_line.startswith(";"):
                    break
                node.properties.append(lines[i].rstrip())
                i += 1
            tscn.nodes.append(node)
            continue

        if line.startswith("[connection"):
            conn = _parse_connection_line(line)
            tscn.connections.append(conn)
            i += 1
            continue

        i += 1

    return tscn


def _parse_header_with_properties(lines: list[str], start: int) -> str:
    header_lines = [lines[start].rstrip()]
    i = start + 1
    while i < len(lines):
        line = lines[i].strip()
        if not line or line.startswith("[") or line.startswith(";"):
            break
        header_lines.append(lines[i].rstrip())
        i += 1
    return "\n".join(header_lines)


def _skip_block(lines: list[str], start: int) -> int:
    i = start + 1
    while i < len(lines):
        line = lines[i].strip()
        if not line and (i + 1 < len(lines) and lines[i + 1].strip().startswith("[")):
            return i + 1
        if line.startswith("[") and i > start:
            return i
        i += 1
    return i


def _parse_node_header_line(line: str) -> NodeEntry:
    inner = _NODE_RE.match(line).group(1)
    name = ""
    parent = None
    node_type = None
    instance = None
    unique_id = None

    name_m = re.search(r'name="([^"]+)"', inner)
    if name_m:
        name = name_m.group(1)

    parent_m = re.search(r'parent="([^"]+)"', inner)
    if parent_m:
        parent = parent_m.group(1)

    type_m = re.search(r'type="([^"]+)"', inner)
    if type_m:
        node_type = type_m.group(1)

    instance_m = re.search(r'instance=ExtResource\("([^"]+)"\)', inner)
    if instance_m:
        instance = f'ExtResource("{instance_m.group(1)}")'

    unique_m = re.search(r'unique_id=(\d+)', inner)
    if unique_m:
        unique_id = int(unique_m.group(1))

    return NodeEntry(
        name=name,
        parent=parent,
        node_type=node_type,
        instance=instance,
        unique_id=unique_id,
    )


def _parse_connection_line(line: str) -> Connection:
    m = _CONNECTION_RE.match(line)
    if not m:
        raise ValueError(f"Cannot parse connection line: {line}")

    flags = None
    flags_m = _CONNECTION_FLAGS_RE.search(line)
    if flags_m:
        flags = int(flags_m.group(1))

    return Connection(
        signal=m.group(1),
        from_path=m.group(2),
        to_path=m.group(3),
        method=m.group(4),
        flags=flags,
    )


def _extract_properties(line: str) -> dict[str, str]:
    props = {}
    for m in re.finditer(r'(\w+)="([^"]*)"', line):
        props[m.group(1)] = m.group(2)
    return props


def update_load_steps(header: str, delta: int = 0) -> str:
    m = re.search(r"load_steps=(\d+)", header)
    if m:
        current = int(m.group(1))
        new_val = current + delta if delta else current
        return re.sub(r"load_steps=\d+", f"load_steps={new_val}", header)
    elif delta:
        return header.replace("[gd_scene", f"[gd_scene load_steps={delta}", 1)
    return header