"""
storage.py – GitHub-backed persistence layer.
All data (users + transactions) lives as JSON files inside the
configured GitHub repository so nothing is lost between deployments.
"""

import json
import base64
from datetime import datetime

import requests
import streamlit as st


class GitHubStorage:
    """Reads and writes JSON files to a GitHub repository via the REST API."""

    USERS_PATH        = "data/users.json"
    TRANSACTIONS_PATH = "data/transactions.json"

    def __init__(self):
        self.token  = st.secrets["github"]["token"]
        self.repo   = st.secrets["github"]["repo"]        # "owner/repo-name"
        self.branch = st.secrets["github"].get("branch", "main")
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept":        "application/vnd.github.v3+json",
        }
        self._base = f"https://api.github.com/repos/{self.repo}/contents"

    # ──────────────────────── low-level helpers ───────────────────────────────

    def _get(self, path: str):
        """Return (parsed_data, sha) or (None, None) if file doesn't exist."""
        url = f"{self._base}/{path}"
        r   = requests.get(url, headers=self.headers, timeout=10)
        if r.status_code == 200:
            raw  = r.json()
            text = base64.b64decode(raw["content"]).decode("utf-8")
            return json.loads(text), raw["sha"]
        return None, None

    def _put(self, path: str, data, sha=None, message: str = "") -> bool:
        """Create or update *path* with *data*. Returns True on success."""
        url     = f"{self._base}/{path}"
        if not message:
            message = f"Update {path} [{datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}]"
        encoded = base64.b64encode(
            json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        ).decode("utf-8")
        body = {"message": message, "content": encoded, "branch": self.branch}
        if sha:
            body["sha"] = sha
        r = requests.put(url, headers=self.headers, json=body, timeout=15)
        return r.status_code in (200, 201)

    # ──────────────────────── users ───────────────────────────────────────────

    def get_users(self):
        data, sha = self._get(self.USERS_PATH)
        return (data or {}), sha

    def save_users(self, users: dict, sha=None) -> bool:
        return self._put(self.USERS_PATH, users, sha, "Update users")

    # ──────────────────────── transactions ───────────────────────────────────

    def get_transactions(self):
        data, sha = self._get(self.TRANSACTIONS_PATH)
        return (data or []), sha

    def save_transactions(self, transactions: list, sha=None) -> bool:
        return self._put(self.TRANSACTIONS_PATH, transactions, sha,
                         "Update transactions")
