"""Local Animation Forge editor. No accounts, providers, or game writes."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import mimetypes
import os
import re
import secrets
import socket
import subprocess
import threading
import tempfile
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

if __package__:
    from . import animation_forge_backends as core
    from . import animation_forge_walk as walk
    from .animation_forge_export import export_project
else:
    import animation_forge_backends as core
    import animation_forge_walk as walk
    from animation_forge_export import export_project

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
WEB = HERE / "animation_forge_web"
DEFAULT_REFERENCE_WALK = REPO.parent.parent.parent / "Documentation/Art/AnimationProofs/night-sky-walk"
WALK_FILES = frozenset({
    "v002/index.html", "v002/playback-data.js", "v002/timed-mannequin-atlas.png",
    "v002/timed-source-atlas.png", "v001/timed-mannequin-atlas.png",
    "v002/preview.mp4", "v002/contact-sheet.png", "v002/README.md",
})
WALK_REQUIRED = frozenset(name for name in WALK_FILES if name.endswith((".html", ".js")) or "atlas" in name)


def canonical(project):
    core.validate_project(project)
    return json.dumps(project, sort_keys=True, indent=2, allow_nan=False).encode("utf-8")


def inside(root, relative):
    candidate = (root / relative).resolve()
    if root.resolve() not in candidate.parents:
        raise ValueError("Path must stay inside the editor's local data directory")
    return candidate


class ForgeStore:
    def __init__(self, root):
        self.root = Path(root).resolve()
        for name in ("projects", "cache", "exports"):
            (self.root / name).mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()

    def projects(self):
        return sorted((p.name for p in (self.root / "projects").glob("*.forge.json")), reverse=True)

    def save(self, project):
        data = canonical(project)
        name = re.sub(r"[^a-zA-Z0-9_-]+", "-", project["name"]).strip("-")[:48] or "untitled"
        name += "-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + secrets.token_hex(3) + ".forge.json"
        path = self.root / "projects" / name
        descriptor, stage_name = tempfile.mkstemp(prefix=".saving-", suffix=".tmp", dir=path.parent)
        stage = Path(stage_name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            # Exclusive create guarantees even a coincident name never replaces a revision.
            os.link(stage, path)
        finally:
            stage.unlink(missing_ok=True)
        return {"file": name, "sha256": hashlib.sha256(data).hexdigest(), "projects": self.projects()}

    def load(self, name):
        path = inside(self.root / "projects", name)
        project = json.loads(path.read_text(encoding="utf-8"))
        canonical(project)
        return project

    def preview(self, project, facing):
        canonical(project)
        if facing not in ("right", "left"):
            raise ValueError("Facing must be right or left")
        frames, diagnostics = {}, {}
        backend = core.backend_for(project)
        renderer_hash = hashlib.sha256(Path(backend.__file__).read_bytes()).hexdigest()
        # Geometry is independent of exposures. Re-timing reuses the same PNGs.
        with self.lock:
            for pose in project["poses"]:
                pair = {}
                for baseline in (False, True):
                    state = core.evaluate_pose(project, pose["id"], baseline=baseline)
                    recipe = {"state": state, "facing": facing,
                              "renderer": renderer_hash}
                    digest = hashlib.sha256(json.dumps(recipe, sort_keys=True, allow_nan=False).encode()).hexdigest()
                    path = self.root / "cache" / (digest + ".png")
                    if not path.exists():
                        png = io.BytesIO()
                        core.render_pose(project, pose["id"], baseline=baseline, facing=facing).save(png, format="PNG")
                        path.write_bytes(png.getvalue())
                    pair["baseline" if baseline else "current"] = "/cache/" + path.name
                    if not baseline:
                        diagnostics[pose["id"]] = state.get("diagnostics", [])
                frames[pose["id"]] = pair
        return {"frames": frames, "diagnostics": diagnostics, "total_ticks": core.total_ticks(project),
                "ground_y": backend.ANCHOR[1]}

    def export(self, project):
        canonical(project)
        name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + secrets.token_hex(3)
        with self.lock:
            result = export_project(project, self.root / "exports" / name)
        return {"directory": str(self.root / "exports" / name), "url": "/exports/" + name + "/index.html", "result": result}


def make_server(root, port=8794, reference_walk=None):
    store = ForgeStore(root)
    token = secrets.token_urlsafe(32)
    walk_root = Path(reference_walk or DEFAULT_REFERENCE_WALK).resolve()

    def walk_available():
        return all(inside(walk_root, name).is_file() for name in WALK_REQUIRED)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send_bytes(self, data, content_type, code=200):
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(data)

        def send_json(self, data, code=200):
            self.send_bytes(json.dumps(data, allow_nan=False).encode(), "application/json; charset=utf-8", code)

        def local_host(self):
            return self.headers.get("Host") in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}

        def do_GET(self):
            try:
                if not self.local_host():
                    return self.send_json({"error": "Local access only"}, 403)
                path = unquote(urlsplit(self.path).path)
                if path == "/api/bootstrap":
                    example = core.default_project()
                    walk_status = walk.availability()
                    library = [{"id": "reach", "title": "Reach · four authored poses", "project": example}]
                    if walk_status["available"]:
                        library.insert(0, {"id": "walk", "title": "Walk · 72 editable poses", "project": walk.default_project()})
                    return self.send_json({"project": library[0]["project"], "example": example, "library": library,
                                           "projects": store.projects(), "token": token,
                                           "data_directory": str(store.root), "app": "other-animation-forge",
                                           "reference_walk": walk_available(), "editable_walk": walk_status})
                if path == "/api/health":
                    return self.send_json({"app": "other-animation-forge", "repo": str(REPO), "data_directory": str(store.root)})
                if path == "/":
                    file = WEB / "index.html"
                elif path in ("/app.js", "/style.css"):
                    file = WEB / path[1:]
                elif path == "/sources":
                    return self.send_bytes((REPO / "docs/animation-forge-sources.md").read_bytes(), "text/plain; charset=utf-8")
                elif path == "/reference-walk":
                    if not walk_available():
                        return self.send_bytes(b"Preserved walk reference unavailable. Start with --reference-walk pointing to the local night-sky-walk directory containing v001 and v002. No motion data is bundled with Forge.", "text/plain; charset=utf-8", 404)
                    file = WEB / "reference-walk.html"
                elif path.startswith("/reference-walk/"):
                    name = path[len("/reference-walk/"):]
                    if name not in WALK_FILES:
                        return self.send_json({"error": "Unknown reference file"}, 404)
                    file = inside(walk_root, name)
                elif path.startswith("/cache/") and path.endswith(".png"):
                    file = inside(store.root / "cache", path[len("/cache/"):])
                elif path.startswith("/exports/"):
                    file = inside(store.root / "exports", path[len("/exports/"):])
                else:
                    return self.send_json({"error": "Not found"}, 404)
                self.send_bytes(file.read_bytes(), mimetypes.guess_type(file.name)[0] or "application/octet-stream")
            except (ValueError, OSError) as exc:
                self.send_json({"error": str(exc)}, 404)

        def do_POST(self):
            try:
                origin = self.headers.get("Origin")
                allowed = {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}
                if not self.local_host() or (origin and origin not in allowed) or self.headers.get("X-Forge-Token") != token:
                    return self.send_json({"error": "Invalid local editor request"}, 403)
                if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    raise ValueError("Expected JSON")
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 1_000_000:
                    raise ValueError("Project request must be between 1 byte and 1 MB")
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError("Expected a request object")
                path = urlsplit(self.path).path
                if path == "/api/preview":
                    result = store.preview(body["project"], body.get("facing", "right"))
                elif path == "/api/validate":
                    canonical(body["project"])
                    result = {"valid": True}
                elif path == "/api/save":
                    result = store.save(body["project"])
                elif path == "/api/load":
                    result = {"project": store.load(body["file"])}
                elif path == "/api/export":
                    result = store.export(body["project"])
                else:
                    return self.send_json({"error": "Not found"}, 404)
                self.send_json(result)
            except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as exc:
                self.send_json({"error": str(exc)}, 400)

    class LocalServer(ThreadingHTTPServer):
        allow_reuse_address = False

        def server_bind(self):
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            super().server_bind()

    server = LocalServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8794)
    parser.add_argument("--data-dir", type=Path, default=REPO / ".forge" / "animation-forge")
    parser.add_argument("--reference-walk", type=Path, default=DEFAULT_REFERENCE_WALK,
                        help="Read-only local proof directory containing preserved v001 and v002")
    args = parser.parse_args()
    server = make_server(args.data_dir, args.port, args.reference_walk)
    print(f"Animation Forge: http://127.0.0.1:{server.server_port}", flush=True)
    print(f"Local projects and exports: {args.data_dir.resolve()}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
