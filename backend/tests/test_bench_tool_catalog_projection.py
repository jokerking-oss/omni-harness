from scripts.benchmark.tool_catalog_projection import compare, fixture


def test_offline_benchmark_uses_production_projection_and_preserves_pairs():
    result = compare()
    assert result["original"]["message_count"] == result["projected"]["message_count"] == 4
    assert result["projected"]["bytes"] < result["original"]["bytes"]
    original, projected = fixture()
    assert original[1].tool_calls == projected[1].tool_calls
    assert original[2].tool_call_id == projected[2].tool_call_id
