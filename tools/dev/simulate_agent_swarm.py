"""Simulate concurrent agent workers competing for AST symbol leases."""
import random

def run_simulation(agents: int = 5, iterations: int = 100):
    collisions = 0
    symbols = ["auth.py", "db.py", "api.py", "worker.py"]
    active = {}
    for _ in range(iterations):
        ag = f"agent_{random.randint(1, agents)}"
        sym = random.choice(symbols)
        if sym in active and active[sym] != ag:
            collisions += 1
        else:
            active[sym] = ag
    print(f"Simulation completed: {collisions} collisions safely blocked.")

if __name__ == "__main__":
    run_simulation()
