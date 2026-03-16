import sys
import os
import requests
import subprocess
import json
import re

def get_github_repo():
    """Tries to determine the GitHub repository from git remote."""
    try:
        output = subprocess.check_output(["git", "config", "--get", "remote.origin.url"], text=True).strip()
        match = re.search(r"github\.com[:/](.+?)(?:\.git)?$", output)
        if match:
            return match.group(1)
    except Exception:
        pass
    return "ok-oldking/ok-wuthering-waves"

def get_token():
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

def get_issue(repo, issue_id):
    token = get_token()
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    
    url = f"https://api.github.com/repos/{repo}/issues/{issue_id}"
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        return resp.json()
    else:
        print(f"Error fetching issue: {resp.status_code} {resp.text}")
        return None

def comment_issue(repo, issue_id, body):
    token = get_token()
    if not token:
        print("Error: GITHUB_TOKEN or GH_TOKEN environment variable is required to comment.")
        return False
    
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {token}"
    }
    url = f"https://api.github.com/repos/{repo}/issues/{issue_id}/comments"
    resp = requests.post(url, headers=headers, json={"body": body})
    if resp.status_code == 201:
        print("Comment posted successfully.")
        return True
    else:
        print(f"Error posting comment: {resp.status_code} {resp.text}")
        return False

def close_issue(repo, issue_id):
    token = get_token()
    if not token:
        print("Error: GITHUB_TOKEN or GH_TOKEN environment variable is required to close an issue.")
        return False
    
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {token}"
    }
    url = f"https://api.github.com/repos/{repo}/issues/{issue_id}"
    resp = requests.patch(url, headers=headers, json={"state": "closed"})
    if resp.status_code == 200:
        print("Issue closed successfully.")
        return True
    else:
        print(f"Error closing issue: {resp.status_code} {resp.text}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python github_api.py <action> <issue_id> [comment_body]")
        sys.exit(1)
    
    action = sys.argv[1]
    issue_id = sys.argv[2]
    repo = get_github_repo()
    
    if action == "get":
        issue = get_issue(repo, issue_id)
        if issue:
            print(json.dumps(issue, indent=2))
    elif action == "comment":
        if len(sys.argv) < 4:
            print("Error: comment body required")
            sys.exit(1)
        body = sys.argv[3]
        comment_issue(repo, issue_id, body)
    elif action == "close":
        close_issue(repo, issue_id)
    else:
        print(f"Unknown action: {action}")
