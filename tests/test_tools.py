import httpx
import pytest
from pydantic import ValidationError
from garmin_connect_mcp.client import GarminClient
from garmin_connect_mcp.tools import Activities, Activity, DateRange, ToolService, sanitize, TOOLS
from conftest import jwt


@pytest.mark.parametrize("args", [{"activity_id": 0}, {"activity_id": "../token"}, {"activity_id": True}, {"activity_id": -1}])
def test_activity_validation(args):
    with pytest.raises(ValidationError):
        Activity.model_validate(args)


@pytest.mark.parametrize("args", [{"limit": 51}, {"limit": 0}, {"offset": -1}, {"activity_type": "x/../token"}, {"api_key": "dont-paste-secrets"}])
def test_list_validation(args):
    with pytest.raises(ValidationError):
        Activities.model_validate(args)


@pytest.mark.parametrize("args", [{"start_date": "2026-11-02", "end_date": "2026-11-01"}, {"start_date": "2026-01-01", "end_date": "2026-02-01"}, {"start_date": "2026-02-30", "end_date": "2026-03-01"}])
def test_range_validation(args):
    with pytest.raises(ValidationError):
        DateRange.model_validate(args)


def test_range_boundary():
    DateRange(start_date="2026-01-01", end_date="2026-01-31")


def test_redaction_preserves_training_data():
    raw = {"startLatitude": 44, "ownerFullName": "Private", "activityId": 42,
           "sets": [{"weight": 30, "repetitions": 8, "position_lat": 123}], "duration": 88,
           "movingDuration": 86, "elapsedDuration": 180, "email": "private", "access_token": "secret"}
    assert sanitize(raw) == {"activityId": 42, "sets": [{"weight": 30, "repetitions": 8}],
                             "duration": 88, "movingDuration": 86, "elapsedDuration": 180}


async def test_activity_pagination_and_detail(settings):
    reads = []
    def handler(req):
        if req.method == "POST":
            return httpx.Response(200, text=jwt())
        reads.append(req)
        return httpx.Response(200, json=[{"activityId": 42, "startLatitude": 11}])
    client = GarminClient(settings, transport=httpx.MockTransport(handler))
    service = ToolService(client)
    output = await service.call("garmin_list_activities", {"limit": 5, "offset": 10, "start_date": "2026-11-01", "activity_type": "strength_training"})
    assert output["data"] == [{"activityId": 42}]
    assert reads[-1].url.path == "/activitylist-service/activities/search/activities"
    assert dict(reads[-1].url.params) == {"limit": "5", "start": "10", "startDate": "2026-11-01", "activityType": "strength_training"}
    await service.call("garmin_get_activity", {"activity_id": 42})
    assert reads[-1].url.path == "/activity-service/activity/42"
    output = await service.call("garmin_get_activity_workouts", {"activity_id": 42})
    assert reads[-1].url.path == "/activity-service/activity/42/workouts"
    assert any("not contain" in n for n in output["notes"])
    await client.aclose()


@pytest.mark.parametrize("metric,path,params", [
    ("weight", "/weight-service/weight/range/2026-11-01/2026-11-05", {"includeAll": "true"}),
    ("steps", "/usersummary-service/stats/steps/daily/2026-11-01/2026-11-05", {}),
    ("stress", "/usersummary-service/stats/stress/daily/2026-11-01/2026-11-05", {}),
    ("hrv", "/hrv-service/hrv/daily/2026-11-01/2026-11-05", {}),
    ("sleep", "/sleep-service/sleep/dailySleepSummariesByDate", {"startDate": "2026-11-01", "endDate": "2026-11-05"}),
    ("body_battery", "/wellness-service/wellness/bodyBattery/reports/daily", {"startDate": "2026-11-01", "endDate": "2026-11-05"}),
    ("daily_summary", "/usersummary-service/v2/dailysummaries", {"startDate": "2026-11-01", "endDate": "2026-11-05"}),
])
async def test_range_endpoint_contract(settings, metric, path, params):
    def handler(req):
        if req.method == "POST":
            return httpx.Response(200, text=jwt())
        assert req.url.path == path
        assert dict(req.url.params) == params
        return httpx.Response(200, json={"data": []})
    client = GarminClient(settings, transport=httpx.MockTransport(handler))
    result = await ToolService(client).call("garmin_get_health_range", {"metric": metric, "start_date": "2026-11-01", "end_date": "2026-11-05"})
    assert result["data"] == {"data": []}
    await client.aclose()


@pytest.mark.parametrize("metric,path,params", [
    ("sleep", "/sleep-service/sleep/dailySleep", {"date": "2026-11-05"}),
    ("hrv", "/hrv-service/hrv/2026-11-05", {}),
    ("heart_rate", "/wellness-service/wellness/dailyHeartRate", {"date": "2026-11-05"}),
])
async def test_day_endpoint_contract(settings, metric, path, params):
    def handler(req):
        if req.method == "POST":
            return httpx.Response(200, text=jwt())
        assert req.url.path == path
        assert dict(req.url.params) == params
        return httpx.Response(204)
    client = GarminClient(settings, transport=httpx.MockTransport(handler))
    result = await ToolService(client).call("garmin_get_day_detail", {"metric": metric, "date": "2026-11-05"})
    assert result["data"] is None
    await client.aclose()


async def test_status_has_no_upstream_call(settings):
    def never(req):
        pytest.fail("status should not contact Garmin")
    client = GarminClient(settings, transport=httpx.MockTransport(never))
    result = await ToolService(client).call("garmin_connector_status", {})
    assert result["data"]["garmin_authenticated"] == "not_checked"
    assert "synthetic-test-key" not in str(result)
    assert len(result["data"]["tools"]) == 6
    await client.aclose()


def test_tool_annotations_and_schema():
    for tool in TOOLS:
        definition = tool.definition()
        assert definition["annotations"]["readOnlyHint"] is True
        assert definition["annotations"]["destructiveHint"] is False
        assert definition["inputSchema"]["additionalProperties"] is False
