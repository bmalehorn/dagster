from dagster import SchedulingCondition

from dagster_tests.definitions_tests.auto_materialize_tests.base_scenario import run_request

from ..scenario_specs import hourly_partitions_def, two_assets_in_sequence
from .asset_condition_scenario import AssetConditionScenarioState


def test_on_cron_unpartitioned() -> None:
    state = AssetConditionScenarioState(
        two_assets_in_sequence,
        asset_condition=SchedulingCondition.on_cron(cron_schedule="0 * * * *"),
    ).with_current_time("2020-02-02T01:05:00")

    # parent hasn't updated yet
    state, result = state.evaluate("B")
    assert result.true_subset.size == 0

    # parent updated, now can execute
    state = state.with_runs(run_request("A"))
    state, result = state.evaluate("B")
    assert result.true_subset.size == 1
    state = state.with_runs(
        *(run_request(ak, pk) for ak, pk in result.true_subset.asset_partitions)
    )

    # now B has been materialized, so don't execute again
    state, result = state.evaluate("B")
    assert result.true_subset.size == 0

    # A gets materialized again before the hour, so don't execute B again
    state = state.with_runs(run_request("A"))
    state, result = state.evaluate("B")
    assert result.true_subset.size == 0

    # now a new cron tick, but A still hasn't been materialized since the hour
    state = state.with_current_time_advanced(hours=1)
    state, result = state.evaluate("B")
    assert result.true_subset.size == 0

    # A gets materialized again after the hour, so execute B again
    state = state.with_runs(run_request("A"))
    state, result = state.evaluate("B")
    assert result.true_subset.size == 1


def test_on_cron_hourly_partitioned() -> None:
    state = (
        AssetConditionScenarioState(
            two_assets_in_sequence,
            asset_condition=SchedulingCondition.on_cron(cron_schedule="0 * * * *"),
        )
        .with_asset_properties(partitions_def=hourly_partitions_def)
        .with_current_time("2020-02-02T01:05:00")
    )

    # parent hasn't updated yet
    state, result = state.evaluate("B")
    assert result.true_subset.size == 0

    # historical parent updated, doesn't matter
    state = state.with_runs(run_request("A", "2019-07-05-00:00"))
    state, result = state.evaluate("B")
    assert result.true_subset.size == 0

    # latest parent updated, now can execute
    state = state.with_runs(run_request("A", "2020-02-02-00:00"))
    state, result = state.evaluate("B")
    assert result.true_subset.size == 1
    state = state.with_runs(
        *(run_request(ak, pk) for ak, pk in result.true_subset.asset_partitions)
    )

    # now B has been materialized, so don't execute again
    state, result = state.evaluate("B")
    assert result.true_subset.size == 0

    # now a new cron tick, but A still hasn't been materialized since the hour
    state = state.with_current_time_advanced(hours=1)
    state, result = state.evaluate("B")
    assert result.true_subset.size == 0

    # A gets materialized with the previous partition after the hour, but that doesn't matter
    state = state.with_runs(run_request("A", "2020-02-02-00:00"))
    state, result = state.evaluate("B")
    assert result.true_subset.size == 0

    # A gets materialized with the latest partition, fire
    state = state.with_runs(run_request("A", "2020-02-02-01:00"))
    state, result = state.evaluate("B")
    assert result.true_subset.size == 1
