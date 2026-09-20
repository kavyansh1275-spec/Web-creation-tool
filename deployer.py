from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


class DeploymentError(RuntimeError):
    pass


class GitHubRenderDeployer:
    """
    Publishes generated projects into a dedicated directory in the Web Creation
    Tool repository and creates a real Render service for that directory.

    Required runtime secrets:
      GITHUB_TOKEN
      RENDER_API_KEY
      RENDER_OWNER_ID   (Render workspace/owner id)

    Optional:
      GITHUB_REPOSITORY (defaults to kavyansh1275-spec/Web-creation-tool)
      GITHUB_BRANCH (defaults to main)
      DEPLOYMENT_BASE_PATH (defaults to generated-sites)
    """

    def __init__(self, project, config=None):
        self.project = Path(project.root).resolve()
        self.config = config
        self.github_token = os.getenv("GITHUB_TOKEN", "").strip()
        self.render_key = os.getenv("RENDER_API_KEY", "").strip()
        self.owner_id = os.getenv("RENDER_OWNER_ID", "").strip()
        self.repository = os.getenv(
            "GITHUB_REPOSITORY", "kavyansh1275-spec/Web-creation-tool"
        ).strip()
        self.branch = os.getenv("GITHUB_BRANCH", "main").strip() or "main"
        self.base_path = os.getenv("DEPLOYMENT_BASE_PATH", "generated-sites").strip("/")

    @property
    def configured(self):
        return bool(self.github_token and self.render_key and self.owner_id)

    @staticmethod
    def slug(value):
        value = re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")
        return value[:48] or "generated-site"

    @staticmethod
    def _request(url, method="GET", token=None, payload=None):
        data = None
        headers = {"Accept": "application/json", "User-Agent": "Web-Creation-Tool"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                raw = response.read().decode("utf-8", errors="replace")
                return response.status, json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise DeploymentError(f"HTTP {exc.code}: {body[:1200]}") from exc
        except urllib.error.URLError as exc:
            raise DeploymentError(f"Network error: {exc}") from exc

    def _github(self, path, method="GET", payload=None):
        return self._request(
            "https://api.github.com" + path,
            method=method,
            token=self.github_token,
            payload=payload,
        )

    def _render(self, path, method="GET", payload=None):
        return self._request(
            "https://api.render.com/v1" + path,
            method=method,
            token=self.render_key,
            payload=payload,
        )

    def _repo_path(self):
        return self.repository.split("/", 1)

    def _existing_sha(self, path):
        owner, repo = self._repo_path()
        try:
            _, data = self._github(
                f"/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}/contents/"
                f"{urllib.parse.quote(path, safe='/')}?ref={urllib.parse.quote(self.branch)}"
            )
            return data.get("sha")
        except DeploymentError as exc:
            if "HTTP 404" in str(exc):
                return None
            raise

    def _commit_file(self, path, content, message):
        owner, repo = self._repo_path()
        raw = content if isinstance(content, bytes) else content.encode("utf-8")
        encoded = base64.b64encode(raw).decode("ascii")
        payload = {"message": message, "content": encoded, "branch": self.branch}
        sha = self._existing_sha(path)
        if sha:
            payload["sha"] = sha
        self._github(
            f"/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}/contents/"
            f"{urllib.parse.quote(path, safe='/')}",
            method="PUT",
            payload=payload,
        )

    def _push_project(self, target):
        files = []
        for path in self.project.rglob("*"):
            if not path.is_file():
                continue
            if ".git" in path.parts or path.name == "qa-screenshot.png":
                continue
            relative = path.relative_to(self.project).as_posix()
            if relative.startswith(".deployment"):
                continue
            files.append((f"{target}/{relative}", path.read_bytes()))
        if not files:
            raise DeploymentError("The generated project contains no deployable files.")
        for path, content in files:
            self._commit_file(path, content, f"Deploy generated project: {self.project.name}")
        return len(files)

    def _render_service(self, service_name, target, kind):
        repo_url = f"https://github.com/{self.repository}"
        if kind == "static":
            details = {
                "buildCommand": "echo 'No build step required'",
                "publishPath": ".",
            }
            payload = {
                "type": "static_site",
                "name": service_name,
                "ownerId": self.owner_id,
                "repo": repo_url,
                "branch": self.branch,
                "autoDeploy": "yes",
                "rootDir": target,
                "serviceDetails": details,
            }
        else:
            details = {
                "runtime": "node",
                "plan": "free",
                "region": "virginia",
                "buildCommand": "npm install",
                "startCommand": "npm start",
            }
            payload = {
                "type": "web_service",
                "name": service_name,
                "ownerId": self.owner_id,
                "repo": repo_url,
                "branch": self.branch,
                "autoDeploy": "yes",
                "rootDir": target,
                "serviceDetails": details,
            }
        _, data = self._render("/services", method="POST", payload=payload)
        service = data.get("service", data)
        return {
            "service_id": service.get("id"),
            "service_name": service.get("name", service_name),
            "url": service.get("url"),
            "slug": service.get("slug"),
        }

    def deploy(self):
        if not self.configured:
            return {
                "success": False,
                "provider": "render",
                "reason": (
                    "Real deployment is not configured. Set GITHUB_TOKEN, "
                    "RENDER_API_KEY and RENDER_OWNER_ID in the Web Creation Tool "
                    "environment."
                ),
            }

        target = f"{self.base_path}/{self.slug(self.project.name)}"
        kind = "static" if (self.project / "index.html").exists() else "web"
        identity = hashlib.sha256(str(self.project).encode("utf-8")).hexdigest()[:8]
        service_name = self.slug(self.project.name) + "-" + identity
        target = target + "-" + identity
        try:
            file_count = self._push_project(target)
            service = self._render_service(service_name, target, kind)
            result = {
                "success": True,
                "provider": "render",
                "kind": kind,
                "repository": f"https://github.com/{self.repository}",
                "branch": self.branch,
                "root_dir": target,
                "files_published": file_count,
                **service,
            }
            (self.project / ".deployment.json").write_text(
                json.dumps(result, indent=2), encoding="utf-8"
            )
            return result
        except Exception as exc:
            return {
                "success": False,
                "provider": "render",
                "reason": str(exc),
                "repository": f"https://github.com/{self.repository}",
                "branch": self.branch,
                "root_dir": target,
            }
