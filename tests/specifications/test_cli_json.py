from sclass.cli_json_output import to_json_summary
def test_summary(): assert 'leases' in to_json_summary(2, 5)
