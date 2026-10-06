from subagent_selector import select_subagents

class SubagentRegistry:
    @staticmethod
    def prepare_full_8_subagent_dispatch(goal_text, fsm_phase, **kwargs):
        profile = kwargs.get("profile", "full")
        domains = kwargs.get("detected_domains")
        plan = select_subagents(phase=fsm_phase, profile=profile, detected_domains=domains)
        return plan.to_dict()

def get_registry():
    return SubagentRegistry
