"""
S-Class Product Demos Runner: Executes all 5 flagship product demos.
"""

import sys
import demo1_false_test_claim
import demo2_dangerous_command
import demo3_secret_exfiltration
import demo4_post_verification_mutation
import demo5_cross_agent_continuity

def main():
    print("\n" + "#" * 70)
    print("#  S-CLASS: THE FIVE FLAGSHIP PRODUCT DEMONSTRATIONS")
    print("#" * 70 + "\n")
    
    demo1_false_test_claim.run()
    demo2_dangerous_command.run()
    demo3_secret_exfiltration.run()
    demo4_post_verification_mutation.run()
    demo5_cross_agent_continuity.run()

    print("#" * 70)
    print("#  ALL 5 PRODUCT DEMONSTRATIONS COMPLETED 100% SUCCESSFULLY")
    print("#" * 70 + "\n")

if __name__ == "__main__":
    main()
