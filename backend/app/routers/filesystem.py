"""Read-only directory browsing for administrator-owned dataset paths."""

import errno
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core import get_current_admin, settings

router = APIRouter(prefix="/api/admin/filesystem", tags=["服务器目录"])


class DirectoryEntry(BaseModel):
    name: str
    path: str


class DirectoryListing(BaseModel):
    path: str
    parent_path: str | None
    roots: list[DirectoryEntry]
    breadcrumbs: list[DirectoryEntry]
    entries: list[DirectoryEntry]
    total: int
    offset: int
    limit: int


def browser_roots() -> list[Path]:
    try:
        roots = list(dict.fromkeys(
            Path(value).resolve(strict=True)
            for value in (settings.FILE_BROWSER_ROOTS or [os.path.abspath(os.sep)])
        ))
        if not all(root.is_dir() for root in roots):
            raise ValueError("not a directory")
        return roots
    except (OSError, ValueError, RuntimeError):
        raise HTTPException(status_code=503, detail="服务器目录浏览范围配置不可用")


def containing_root(path: Path, roots: list[Path]) -> Path | None:
    return next((root for root in sorted(roots, key=lambda p: len(p.parts), reverse=True)
                 if path.is_relative_to(root)), None)


@router.get("/directories", response_model=DirectoryListing)
def list_directories(
    path: str | None = Query(None, max_length=4096),
    search: str = Query("", max_length=255),
    show_hidden: bool = False,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_admin=Depends(get_current_admin),
):
    roots = browser_roots()
    requested = Path(path) if path else roots[0]
    if not requested.is_absolute() or "\x00" in str(requested):
        raise HTTPException(status_code=400, detail="请填写服务器上的绝对目录路径")
    try:
        # Resolve aliases such as /tmp -> /private/tmp before checking the boundary.
        directory = requested.resolve(strict=False)
        root = containing_root(directory, roots)
        if root is None:
            raise HTTPException(status_code=403, detail="该路径不在允许浏览的服务器目录范围内")
        directory = directory.resolve(strict=True)
        entries = []
        with os.scandir(directory) as children:
            for child in children:
                if (not show_hidden and child.name.startswith(".")) or search.casefold() not in child.name.casefold():
                    continue
                try:
                    if not child.is_dir():
                        continue
                    target = Path(child.path).resolve(strict=True)
                    if containing_root(target, roots):
                        entries.append(DirectoryEntry(name=child.name, path=str(target)))
                except (OSError, RuntimeError):
                    # Broken links or children disappearing during enumeration are not navigable.
                    continue
        entries.sort(key=lambda entry: (entry.name.casefold(), entry.name))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="服务器目录不存在，可能已被移动或删除")
    except NotADirectoryError:
        raise HTTPException(status_code=400, detail="该服务器路径不是目录")
    except OSError as error:
        if error.errno in (errno.EACCES, errno.EPERM):
            raise HTTPException(status_code=403, detail="服务账号没有读取此服务器目录的权限")
        raise HTTPException(status_code=400, detail="无法读取此服务器目录，请检查路径或挂载状态")
    except (ValueError, RuntimeError):
        raise HTTPException(status_code=400, detail="服务器目录路径无效")

    def entry(value: Path) -> DirectoryEntry:
        return DirectoryEntry(name=value.name or value.anchor, path=str(value))

    breadcrumbs = [root]
    for part in directory.relative_to(root).parts:
        breadcrumbs.append(breadcrumbs[-1] / part)
    return DirectoryListing(
        path=str(directory),
        parent_path=str(directory.parent) if directory != root else None,
        roots=[entry(value) for value in roots],
        breadcrumbs=[entry(value) for value in breadcrumbs],
        entries=entries[offset:offset + limit],
        total=len(entries), offset=offset, limit=limit,
    )
