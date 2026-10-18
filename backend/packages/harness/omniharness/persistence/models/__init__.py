"""ORM model registration entry point.

Importing this module ensures all ORM models are registered with
``Base.metadata`` so Alembic autogenerate detects every table.

The actual ORM classes have moved to entity-specific subpackages:
- ``omniharness.persistence.thread_meta``
- ``omniharness.persistence.run``
- ``omniharness.persistence.feedback``
- ``omniharness.persistence.user``

``RunEventRow`` remains in ``omniharness.persistence.models.run_event`` because
its storage implementation lives in ``omniharness.runtime.events.store.db`` and
there is no matching entity directory.
"""

from omniharness.persistence.agents.model import AgentRow
from omniharness.persistence.channel_connections.model import (
    ChannelConnectionRow,
    ChannelConversationRow,
    ChannelCredentialRow,
    ChannelOAuthStateRow,
)
from omniharness.persistence.feedback.model import FeedbackRow
from omniharness.persistence.managed_subagents.model import ManagedSubagentRow
from omniharness.persistence.mcp_tasks.model import McpTaskRow
from omniharness.persistence.models.run_event import RunEventRow
from omniharness.persistence.personal_access_tokens.model import PersonalAccessTokenRow
from omniharness.persistence.projects.model import ProjectDocumentRow, ProjectRow
from omniharness.persistence.run.model import RunChangeClockRow, RunRow
from omniharness.persistence.scheduled_task_runs.model import ScheduledTaskRunRow
from omniharness.persistence.scheduled_tasks.model import ScheduledTaskRow
from omniharness.persistence.subagent_batches.model import SubagentBatchItemRow, SubagentBatchRow
from omniharness.persistence.thread_meta.model import ThreadMetaRow
from omniharness.persistence.user.model import UserPreferenceRow, UserRow
from omniharness.persistence.webhook_delivery.model import WebhookDeliveryRow

__all__ = [
    "AgentRow",
    "ChannelConnectionRow",
    "ChannelConversationRow",
    "ChannelCredentialRow",
    "ChannelOAuthStateRow",
    "FeedbackRow",
    "McpTaskRow",
    "ManagedSubagentRow",
    "PersonalAccessTokenRow",
    "ProjectDocumentRow",
    "ProjectRow",
    "RunEventRow",
    "RunChangeClockRow",
    "RunRow",
    "ScheduledTaskRow",
    "ScheduledTaskRunRow",
    "SubagentBatchRow",
    "SubagentBatchItemRow",
    "ThreadMetaRow",
    "UserPreferenceRow",
    "UserRow",
    "WebhookDeliveryRow",
]
