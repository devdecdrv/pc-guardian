"""
PC Guardian — File Manager
Read and write files on the PC via Telegram commands
Password protected: decdrv
"""

import os
import logging
import tempfile
import shutil
import glob

logger = logging.getLogger("file_manager")

UNLOCK_PASSWORD = "decdrv"
MAX_READ_SIZE   = 5 * 1024 * 1024   # 5 MB read limit
FORBIDDEN       = [
    "config.enc", ".key", "config\\", "config/"  # never expose these
]


def _is_forbidden(path: str) -> bool:
    for f in FORBIDDEN:
        if f.lower() in path.lower():
            return True
    return False


class FileManager:
    def __init__(self, cfg):
        self.cfg = cfg

    def read_file(self, path: str) -> tuple:
        """
        Returns (content_bytes, error_str).
        content_bytes is None on error.
        """
        path = os.path.expandvars(os.path.expanduser(path))
        if _is_forbidden(path):
            return None, "Access to that file is restricted."
        if not os.path.exists(path):
            return None, f"File not found: {path}"
        if os.path.isdir(path):
            return None, f"That's a directory. Use /ls to list it."
        size = os.path.getsize(path)
        if size > MAX_READ_SIZE:
            return None, f"File too large ({size//1024}KB). Max 5MB."
        try:
            with open(path, "rb") as f:
                return f.read(), None
        except PermissionError:
            return None, "Permission denied."
        except Exception as e:
            return None, str(e)

    def write_file(self, path: str, content: bytes) -> tuple:
        """
        Returns (success: bool, message: str).
        """
        path = os.path.expandvars(os.path.expanduser(path))
        if _is_forbidden(path):
            return False, "Cannot write to that path."
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "wb") as f:
                f.write(content)
            return True, f"Written: {path} ({len(content)} bytes)"
        except PermissionError:
            return False, "Permission denied."
        except Exception as e:
            return False, str(e)

    def list_dir(self, path: str) -> tuple:
        """List directory contents."""
        path = os.path.expandvars(os.path.expanduser(path.strip() or "C:\\Users"))
        if not os.path.exists(path):
            return None, f"Path not found: {path}"
        if not os.path.isdir(path):
            return None, f"Not a directory: {path}"
        try:
            entries = os.listdir(path)
            lines = []
            for e in sorted(entries)[:50]:  # cap at 50 entries
                full = os.path.join(path, e)
                tag  = "📁" if os.path.isdir(full) else "📄"
                try:
                    size = "" if os.path.isdir(full) else f" ({os.path.getsize(full)//1024}KB)"
                except Exception:
                    size = ""
                lines.append(f"{tag} {e}{size}")
            if len(entries) > 50:
                lines.append(f"... and {len(entries)-50} more")
            return "\n".join(lines), None
        except PermissionError:
            return None, "Permission denied."
        except Exception as e:
            return None, str(e)

    def delete_file(self, path: str) -> tuple:
        path = os.path.expandvars(os.path.expanduser(path))
        if _is_forbidden(path):
            return False, "Cannot delete that file."
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            return True, f"Deleted: {path}"
        except Exception as e:
            return False, str(e)

    def search_files(self, pattern: str, root: str = "C:\\Users") -> list:
        """Glob search for files matching pattern."""
        root = os.path.expandvars(os.path.expanduser(root))
        try:
            results = glob.glob(
                os.path.join(root, "**", pattern),
                recursive=True
            )
            return results[:20]  # cap results
        except Exception:
            return []
