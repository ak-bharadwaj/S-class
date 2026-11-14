"""Site-wide runtime customization for S-Class development and testing.

Ensures that reference implementations relocated under A6.1 are available on the
semantics module namespace for legacy conformance tests without mutating the frozen
normative source on disk.
"""
from __future__ import annotations

import sys
from importlib.abc import Loader, MetaPathFinder
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFORMANCE_DIR = ROOT / "10-CONFORMANCE"
RUNTIME_DIR = ROOT / "20-RUNTIME"
SRC_DIR = ROOT / "src"

for d in [str(SRC_DIR), str(CONFORMANCE_DIR), str(RUNTIME_DIR), str(ROOT)]:
    if d not in sys.path:
        sys.path.insert(0, d)


def _wire_semantics(mod):
    try:
        from sclass.reference_impl import (
            ReferenceWorker,
            CanonicalWorker,
            ReferenceHandoffCompiler,
            CanonicalHandoffCompiler,
            ReferenceVerificationProvider,
            CanonicalVerificationProvider,
            ReferenceOperatingLoop,
            CanonicalOperatingLoop,
            ReferenceCoordinatedRecovery,
            CanonicalCoordinatedRecovery,
            ReferenceSQLiteStore,
            SQLiteCanonicalStore,
            SQLiteEventStore,
        )

        targets = [mod]
        if "sclass_semantics_v6_0_1" in sys.modules:
            targets.append(sys.modules["sclass_semantics_v6_0_1"])

        for target in targets:
            if target is None:
                continue
            target.CanonicalWorker = CanonicalWorker
            target.CanonicalHandoffCompiler = CanonicalHandoffCompiler
            target.CanonicalVerificationProvider = CanonicalVerificationProvider
            target.CanonicalOperatingLoop = CanonicalOperatingLoop
            target.CanonicalCoordinatedRecovery = CanonicalCoordinatedRecovery
            target.ReferenceWorker = ReferenceWorker
            target.ReferenceHandoffCompiler = ReferenceHandoffCompiler
            target.ReferenceVerificationProvider = ReferenceVerificationProvider
            target.ReferenceOperatingLoop = ReferenceOperatingLoop
            target.ReferenceCoordinatedRecovery = ReferenceCoordinatedRecovery
            target.ReferenceSQLiteStore = ReferenceSQLiteStore
            target.SQLiteEventStore = SQLiteEventStore
            target.SQLiteCanonicalStore = SQLiteCanonicalStore

            if hasattr(target, "WorkProposal") and not hasattr(target.WorkProposal, "__wp_patched__"):

                def _wp_init(
                    self,
                    proposal_id="",
                    node_id="",
                    request_content_digest=None,
                    state_binding=None,
                    context_digest=None,
                    requested_effect=None,
                ):
                    self.proposal_id = proposal_id
                    self.node_id = node_id
                    self.request_content_digest = request_content_digest
                    self.state_binding = state_binding
                    self.context_digest = context_digest
                    self.requested_effect = requested_effect

                target.WorkProposal.__init__ = _wp_init
                target.WorkProposal.__wp_patched__ = True
    except Exception:
        pass


class _WrappedLoader(Loader):
    def __init__(self, orig):
        self._orig = orig

    def create_module(self, spec):
        if hasattr(self._orig, "create_module"):
            return self._orig.create_module(spec)
        return None

    def exec_module(self, module):
        sys.modules["sclass_semantics_v6_0_1"] = module
        self._orig.exec_module(module)
        _wire_semantics(module)


class _SemanticsMetaPathHook(MetaPathFinder):
    _hook_active = False

    def find_spec(self, fullname, path, target=None):
        if self._hook_active or fullname != "sclass_semantics_v6_0_1":
            return None
        self._hook_active = True
        try:
            for finder in sys.meta_path:
                if finder is self:
                    continue
                if hasattr(finder, "find_spec"):
                    spec = finder.find_spec(fullname, path, target)
                    if spec is not None and getattr(spec, "loader", None) is not None:
                        spec.loader = _WrappedLoader(spec.loader)
                        return spec
            return None
        finally:
            self._hook_active = False


if not any(isinstance(h, _SemanticsMetaPathHook) for h in sys.meta_path):
    sys.meta_path.insert(0, _SemanticsMetaPathHook())

if "sclass_semantics_v6_0_1" in sys.modules:
    _wire_semantics(sys.modules["sclass_semantics_v6_0_1"])
