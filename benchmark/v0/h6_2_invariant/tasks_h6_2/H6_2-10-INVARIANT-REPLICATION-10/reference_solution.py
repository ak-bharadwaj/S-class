class InvariantErr(Exception): pass
class ModuleV2_10:
    def check_invariant(self, p: dict) -> bool:
        if not isinstance(p, dict) or p.get('valid') is not True:
            raise InvariantErr('Invalid')
        return True
