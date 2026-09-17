"""Utility to verify all structural contracts export frozen dataclasses."""
import inspect
from sclass.contracts import evidence_contracts, lease_contracts, policy_contracts, telemetry_contracts

def verify_module_dataclasses(mod):
    for name, obj in inspect.getmembers(mod, inspect.isclass):
        if hasattr(obj, "__dataclass_params__"):
            assert obj.__dataclass_params__.frozen is True, f"{name} must be frozen"

if __name__ == "__main__":
    for m in [evidence_contracts, lease_contracts, policy_contracts, telemetry_contracts]:
        verify_module_dataclasses(m)
    print("All contracts verified frozen.")
