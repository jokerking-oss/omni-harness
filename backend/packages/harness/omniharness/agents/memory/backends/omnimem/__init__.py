"""OmniMem backend -- the default memory manager (self-contained).

Holds its own manager class (:mod:`omni_mem`) plus a ``core/`` folder with
the five functional modules (storage / queue / updater / prompt /
message_processing). All OmniMem-private logic lives here; the shared
package top only carries the contract + factory + thin entry points.
"""

from .omni_mem import OmniMem

#: The :class:`~omniharness.agents.memory.manager.MemoryManager` subclass this
#: backend exposes. Discovered by the factory's ``_scan_backends`` drop-in
#: mechanism under the folder name ``omnimem``.
MANAGER_CLASS = OmniMem
