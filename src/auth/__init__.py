"""
Authentication module for ComputeSwarm
Provides GitHub OAuth and wallet-based authentication
"""

from src.auth.github import GitHubOAuth, GitHubUser

__all__ = ["GitHubOAuth", "GitHubUser"]

