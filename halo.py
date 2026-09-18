#!/usr/bin/env python3
"""HALO - Commit Your Thoughts

A standard-library-only project logging and console utility.

The original design is preserved around two main concepts:
- NewHalo: create and register a project log.
- ConsoleC: interactive console for managing projects and logs.

Storage layout:
    ~/Documents/Logs/
    ├── Parent.log       # JSON index of all projects
    ├── ProjectA.log     # Human-readable project log
    └── ProjectB.log

No third-party packages are required.
"""

import datetime
import json
import logging
import os
import re
import shlex
import sys
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# HALO: COMMIT YOUR THOUGHTS

__all__ = ["Console", "NewHalo"]

__commands__ = [
    "help",
    "new",
    "list",
    "open",
    "log",
    "info",
    "search",
    "remove",
    "status",
    "clear",
    "exit",
]

__description__ = "HALO - a lightweight project log and thought-commit console."

__cmsg__ = """
Copyright © 2026 Naman Kumar. Halo Console.
"""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

try:
    env = os.environ.get("HOME") or str(Path.home())
except Exception:
    env = os.getcwd()


LOG = logging.getLogger("halo")
LOG.addHandler(logging.NullHandler())

APP_VERSION = "1.0.0"
ENCODING = "utf-8"
PARENT_VERSION = 1
LOG_HEADER = "HALO PROJECT LOG"


def _utc_iso() -> str:
    """Return an ISO timestamp in UTC."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _local_iso() -> str:
    """Return an ISO timestamp in local time."""
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def _safe_name(name: str) -> str:
    """Convert a project name into a safe single filename stem."""
    name = name.strip()
    if not name:
        raise ValueError("Project name cannot be empty.")

    # Keep useful punctuation but remove path separators and control chars.
    name = name.replace("/", "_").replace("\\", "_")
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name)
    name = re.sub(r"\s+", " ", name).strip(" .")

    if not name:
        raise ValueError("Project name contains no usable characters.")
    if name.lower() == "parent":
        raise ValueError("'Parent' is reserved by HALO.")

    return name


def _atomic_write_text(path: Path, data: str) -> None:
    """Atomically replace a text file using only the standard library."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    try:
        temp.write_text(data, encoding=ENCODING)
        os.replace(temp, path)
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def _atomic_write_json(path: Path, data: Any) -> None:
    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    _atomic_write_text(path, payload)


class NewHalo:
    """Create and register a new HALO project log."""

    def __init__(self, name: str, version: str, term: Optional[str] = None):
        self.__dir = Path(env) / "Documents" / "Logs"
        self.__parent = self.__dir / "Parent.log"
        self.__name = _safe_name(name)
        self.__intime = datetime.datetime.now().astimezone()
        self.__file = self.__dir / f"{self.__name}.log"
        self.__version = str(version).strip() or APP_VERSION
        self.__terminal_date = term  # no terminal date if not given

        self.__dir.mkdir(parents=True, exist_ok=True)
        self._ensure_parent()
        self._update_parent()
        self._create_log()

        print(f"Project '{self.__name}' created successfully!")
        print(f"Log: {self.__file}")

    @property
    def name(self) -> str:
        return self.__name

    @property
    def path(self) -> Path:
        return self.__file

    @property
    def version(self) -> str:
        return self.__version

    @property
    def created_at(self) -> str:
        return self.__intime.isoformat(timespec="seconds")

    def _ensure_parent(self) -> Dict[str, Any]:
        if not self.__parent.exists():
            parent = {
                "halo": {
                    "name": "HALO",
                    "version": APP_VERSION,
                    "format_version": PARENT_VERSION,
                    "created_at": _local_iso(),
                    "updated_at": _local_iso(),
                },
                "project_count": 0,
                "projects": [],
            }
            _atomic_write_json(self.__parent, parent)
            return parent

        try:
            parent = json.loads(self.__parent.read_text(encoding=ENCODING))
        except (json.JSONDecodeError, OSError):
            # Preserve corrupted data rather than silently destroying it.
            backup = self.__parent.with_suffix(
                self.__parent.suffix + f".corrupt-{datetime.datetime.now():%Y%m%d%H%M%S}"
            )
            try:
                os.replace(self.__parent, backup)
            except OSError:
                pass
            parent = {
                "halo": {
                    "name": "HALO",
                    "version": APP_VERSION,
                    "format_version": PARENT_VERSION,
                    "created_at": _local_iso(),
                    "updated_at": _local_iso(),
                },
                "project_count": 0,
                "projects": [],
            }
            _atomic_write_json(self.__parent, parent)
            return parent

        parent.setdefault("halo", {})
        parent["halo"].setdefault("name", "HALO")
        parent["halo"].setdefault("version", APP_VERSION)
        parent["halo"].setdefault("format_version", PARENT_VERSION)
        parent.setdefault("projects", [])
        parent.setdefault("project_count", len(parent["projects"]))
        return parent

    def _create_log(self) -> None:
        """Create the individual project log with a readable initial entry."""
        if self.__file.exists():
            raise FileExistsError(f"Project log already exists: {self.__file}")

        lines = [
            LOG_HEADER,
            "=" * len(LOG_HEADER),
            f"Project: {self.__name}",
            f"Version: {self.__version}",
            f"Created: {self.created_at}",
            f"HALO: {APP_VERSION}",
        ]
        if self.__terminal_date:
            lines.append(f"Terminal date: {self.__terminal_date}")
        lines.extend(
            [
                "",
                "[SYSTEM] Project initialized.",
                "",
            ]
        )
        _atomic_write_text(self.__file, "\n".join(lines))

    def _update_parent(self) -> None:
        """Register this project in Parent.log."""
        parent = self._ensure_parent()
        projects: List[Dict[str, Any]] = parent.setdefault("projects", [])

        if any(p.get("name") == self.__name for p in projects):
            raise FileExistsError(f"Project '{self.__name}' is already registered.")

        projects.append(
            {
                "name": self.__name,
                "version": self.__version,
                "file": self.__file.name,
                "created_at": self.created_at,
                "terminal_date": self.__terminal_date,
                "entries": 1,
                "status": "active",
            }
        )
        projects.sort(key=lambda p: p.get("name", "").lower())
        parent["project_count"] = len(projects)
        parent["halo"]["updated_at"] = _local_iso()
        _atomic_write_json(self.__parent, parent)


class ConsoleC:
    """Interactive HALO command console."""

    def __init__(self):
        self.__dir = Path(env) / "Documents" / "Logs"
        self.__parent = self.__dir / "Parent.log"
        self.__parent_data: Dict[str, Any] = {}
        self.__os_info: Dict[str, Any] = {}
        self.__info: Dict[str, Any] = {}
        self.__running = True
        self.__dir.mkdir(parents=True, exist_ok=True)
        self._load_parent()
        self._load_os()
        self._load_info()
        self._check_for_irregularities()  # raises error if irregularities

    def _default_parent(self) -> Dict[str, Any]:
        now = _local_iso()
        return {
            "halo": {
                "name": "HALO",
                "version": APP_VERSION,
                "format_version": PARENT_VERSION,
                "created_at": now,
                "updated_at": now,
            },
            "project_count": 0,
            "projects": [],
        }

    def _load_parent(self) -> None:
        if not self.__parent.exists():
            self.__parent_data = self._default_parent()
            _atomic_write_json(self.__parent, self.__parent_data)
            return

        try:
            self.__parent_data = json.loads(
                self.__parent.read_text(encoding=ENCODING)
            )
        except (json.JSONDecodeError, OSError) as exc:
            raise RuntimeError(
                f"Unable to load Parent.log: {exc}"
            ) from exc

        if not isinstance(self.__parent_data, dict):
            raise RuntimeError("Parent.log must contain a JSON object.")

    def _load_os(self) -> None:
        # Kept intentionally standard-library-only.
        self.__os_info = {
            "platform": sys.platform,
            "python": sys.version.split()[0],
            "executable": sys.executable,
            "cwd": os.getcwd(),
            "home": env,
            "pid": os.getpid(),
            "terminal": os.environ.get("TERM", "unknown"),
        }

    def _load_info(self) -> None:
        projects = self.__parent_data.get("projects", [])
        existing = sum(
            1
            for item in projects
            if (self.__dir / item.get("file", "")).is_file()
        )
        self.__info = {
            "log_directory": str(self.__dir),
            "parent_log": str(self.__parent),
            "project_count": len(projects),
            "registered_files_found": existing,
        }

    def _check_for_irregularities(self) -> List[str]:
        """Return detected consistency problems without destroying user data."""
        irregularities: List[str] = []
        projects = self.__parent_data.get("projects")

        if not isinstance(projects, list):
            irregularities.append("Parent.log field 'projects' is not a list.")
            return irregularities

        expected_count = len(projects)
        if self.__parent_data.get("project_count") != expected_count:
            irregularities.append(
                f"project_count is {self.__parent_data.get('project_count')}, "
                f"but {expected_count} projects are registered."
            )

        names = set()
        for project in projects:
            name = project.get("name")
            file_name = project.get("file")
            if not name or not file_name:
                irregularities.append("A project entry is missing name or file.")
                continue
            if name in names:
                irregularities.append(f"Duplicate project registration: {name}")
            names.add(name)
            if not (self.__dir / file_name).is_file():
                irregularities.append(f"Missing log file for project: {name}")

        registered = {
            p.get("file")
            for p in projects
            if isinstance(p, dict) and p.get("file")
        }
        for file in self.__dir.glob("*.log"):
            if file.name == self.__parent.name:
                continue
            if file.name not in registered:
                irregularities.append(f"Unregistered log file: {file.name}")

        return irregularities

    # ------------------------------------------------------------------
    # Console commands
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the interactive console."""
        self.__running = True
        self._banner()

        while self.__running:
            try:
                raw = input("halo> ").strip()
            except EOFError:
                print()
                break
            except KeyboardInterrupt:
                print("^C")
                continue

            if not raw:
                continue

            try:
                self.handlecommand(raw)
            except Exception as exc:  # console should not die on user input
                print(f"Error: {exc}")

    def _banner(self) -> None:
        print()
        print("HALO — COMMIT YOUR THOUGHTS")
        print(f"Version {APP_VERSION}")
        print(f"Logs: {self.__dir}")
        print("Type 'help' for commands.")
        print()

    def new(self, args: Optional[List[str]] = None) -> None:
        """Create a project: new <name> [version] [terminal-date]."""
        args = args or []
        if not args:
            name = input("Project name: ").strip()
        else:
            name = " ".join(args[:1])

        if not name:
            print("Project name cannot be empty.")
            return

        version = args[1] if len(args) > 1 else input("Version [1.0]: ").strip() or "1.0"
        term = " ".join(args[2:]).strip() if len(args) > 2 else None

        try:
            NewHalo(name, version, term)
        except Exception as exc:
            print(f"Could not create project: {exc}")
            return

        self._refresh()

    def help(self, _args: Optional[List[str]] = None) -> None:
        print(
            textwrap.dedent(
                """
                HALO commands
                -------------
                help                         Show this help.
                new <name> [version]        Create a new project.
                list                         List registered projects.
                open <name>                  Display a project's log.
                log <name> <thought>         Commit a thought to a project.
                info <name>                  Show project metadata.
                search <text>                Search all project logs.
                remove <name>                Remove a project registration/log.
                status                       Check Parent.log consistency.
                clear                        Clear the terminal.
                exit / quit                  Leave HALO.

                Examples:
                  new Maverick 1.0
                  log Maverick "Implemented camera tracking"
                  open Maverick
                  search "camera"
                """
            ).strip()
        )

    def list(self, _args: Optional[List[str]] = None) -> None:
        projects = self.__parent_data.get("projects", [])
        if not projects:
            print("No HALO projects registered.")
            return

        print()
        print(f"{'PROJECT':<24} {'VERSION':<10} {'STATUS':<10} {'ENTRIES':>7}")
        print("-" * 58)
        for project in sorted(projects, key=lambda x: x.get("name", "").lower()):
            print(
                f"{project.get('name', '')[:23]:<24} "
                f"{project.get('version', '')[:9]:<10} "
                f"{project.get('status', 'unknown')[:9]:<10} "
                f"{str(project.get('entries', 0)):>7}"
            )
        print()

    def open(self, args: Optional[List[str]] = None) -> None:
        if not args:
            print("Usage: open <project>")
            return

        name = " ".join(args)
        project = self._find_project(name)
        if not project:
            print(f"Project not found: {name}")
            return

        path = self.__dir / project["file"]
        if not path.is_file():
            print(f"Log file is missing: {path}")
            return

        print()
        print(path.read_text(encoding=ENCODING), end="")
        if not path.read_text(encoding=ENCODING).endswith("\n"):
            print()

    def log(self, args: Optional[List[str]] = None) -> None:
        if not args or len(args) < 2:
            print("Usage: log <project> <thought>")
            return

        project_token = args[0]
        project = self._find_project(project_token)
        if not project:
            # Permit multi-word project names by finding the longest prefix.
            project, project_token, thought = self._resolve_log_args(args)
        else:
            thought = " ".join(args[1:])

        if not project:
            print(f"Project not found: {project_token}")
            return
        if not thought.strip():
            print("Thought cannot be empty.")
            return

        self._append_entry(project, thought.strip())
        print(f"Committed to {project['name']}.")
        self._refresh()

    def info(self, args: Optional[List[str]] = None) -> None:
        if not args:
            print("Usage: info <project>")
            return

        project = self._find_project(" ".join(args))
        if not project:
            print(f"Project not found: {' '.join(args)}")
            return

        print()
        for key, value in project.items():
            print(f"{key:<15}: {value}")
        print(f"path           : {self.__dir / project['file']}")

    def search(self, args: Optional[List[str]] = None) -> None:
        if not args:
            print("Usage: search <text>")
            return
        query = " ".join(args).lower()
        found = 0

        for project in self.__parent_data.get("projects", []):
            path = self.__dir / project.get("file", "")
            if not path.is_file():
                continue
            try:
                lines = path.read_text(encoding=ENCODING).splitlines()
            except OSError:
                continue

            for number, line in enumerate(lines, start=1):
                if query in line.lower():
                    print(f"{project.get('name', path.stem)}:{number}: {line}")
                    found += 1

        if not found:
            print(f"No results for: {query}")

    def remove(self, args: Optional[List[str]] = None) -> None:
        if not args:
            print("Usage: remove <project>")
            return

        name = " ".join(args)
        project = self._find_project(name)
        if not project:
            print(f"Project not found: {name}")
            return

        path = self.__dir / project["file"]
        answer = input(
            f"Remove project '{project['name']}' and its log? [y/N]: "
        ).strip().lower()
        if answer != "y":
            print("Cancelled.")
            return

        if path.exists():
            path.unlink()

        self.__parent_data["projects"] = [
            p for p in self.__parent_data.get("projects", [])
            if p.get("name") != project.get("name")
        ]
        self.__parent_data["project_count"] = len(self.__parent_data["projects"])
        self.__parent_data.setdefault("halo", {})["updated_at"] = _local_iso()
        _atomic_write_json(self.__parent, self.__parent_data)
        self._refresh()
        print(f"Removed '{project['name']}'.")

    def status(self, _args: Optional[List[str]] = None) -> None:
        irregularities = self._check_for_irregularities()
        if not irregularities:
            print("HALO status: OK")
            print(f"Projects: {len(self.__parent_data.get('projects', []))}")
            print(f"Directory: {self.__dir}")
            return

        print("HALO status: IRREGULARITIES DETECTED")
        for item in irregularities:
            print(f"- {item}")

    def clear(self, _args: Optional[List[str]] = None) -> None:
        command = "cls" if os.name == "nt" else "clear"
        os.system(command)

    def handlecommand(self, command: str) -> None:
        """Parse and dispatch one console command."""
        try:
            parts = shlex.split(command)
        except ValueError as exc:
            print(f"Invalid command syntax: {exc}")
            return

        if not parts:
            return

        cmd = parts[0].lower()
        args = parts[1:]

        aliases = {
            "ls": "list",
            "quit": "exit",
            "q": "exit",
            "?": "help",
            "rm": "remove",
        }
        cmd = aliases.get(cmd, cmd)

        if cmd == "exit":
            self.__running = False
            print("HALO closed.")
            return

        method = getattr(self, cmd, None)
        if method is None or cmd.startswith("_"):
            print(f"Unknown command: {cmd}. Type 'help'.")
            return

        method(args)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_project(self, name: str) -> Optional[Dict[str, Any]]:
        normalized = name.strip().casefold()
        for project in self.__parent_data.get("projects", []):
            if str(project.get("name", "")).casefold() == normalized:
                return project
        return None

    def _resolve_log_args(
        self, args: List[str]
    ) -> Tuple[Optional[Dict[str, Any]], str, str]:
        """Resolve 'log multi word project thought' by longest project prefix."""
        projects = sorted(
            self.__parent_data.get("projects", []),
            key=lambda p: len(str(p.get("name", "")).split()),
            reverse=True,
        )
        joined = " ".join(args)
        for project in projects:
            prefix = str(project.get("name", ""))
            if joined.casefold().startswith(prefix.casefold() + " "):
                thought = joined[len(prefix):].strip()
                return project, prefix, thought
        return None, args[0], ""

    def _append_entry(self, project: Dict[str, Any], thought: str) -> None:
        path = self.__dir / project["file"]
        if not path.is_file():
            raise FileNotFoundError(f"Project log does not exist: {path}")

        timestamp = _local_iso()
        with path.open("a", encoding=ENCODING, newline="\n") as handle:
            handle.write(f"[{timestamp}] {thought}\n")

        project["entries"] = int(project.get("entries", 0)) + 1
        project["last_entry"] = timestamp
        self.__parent_data.setdefault("halo", {})["updated_at"] = timestamp
        _atomic_write_json(self.__parent, self.__parent_data)

    def _refresh(self) -> None:
        self._load_parent()
        self._load_info()


# ---------------------------------------------------------------------------
# Application entry point
# ---------------------------------------------------------------------------


def main() -> int:
    try:
        Console = ConsoleC()
    except Exception as exc:
        print(f"HALO startup error: {exc}", file=sys.stderr)
        return 1

    Console.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
