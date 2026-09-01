from pydantic import BaseModel


class ArtifactItem(BaseModel):
    name: str
    rel: str
    size: int
    mtime: str
    kind: str


class ExternalArtifact(BaseModel):
    abs_path: str
    tool: str
    ts: str = ""
    exists: bool


class ArtifactListResponse(BaseModel):
    items: list[ArtifactItem]
    external: list[ExternalArtifact]
    count: int
    truncated: bool
    root: str


class RevealRequest(BaseModel):
    rel: str | None = None
    abs_path: str | None = None
