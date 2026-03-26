"""Domain agent package for GiskardFoundry."""

from .base import Agent
from .gtd_agent import GTDAgent
from .jobsearch_agent import JobSearchAgent
from .onenote_agent import OneNoteAgent

__all__ = [
    "Agent",
    "OneNoteAgent",
    "GTDAgent",
    "JobSearchAgent",
]
