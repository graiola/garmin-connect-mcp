"""Small, explicitly allowlisted read tools; no URL, method or credentials in tool inputs."""
from __future__ import annotations
import asyncio
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Literal
from zoneinfo import ZoneInfo
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .client import GarminClient
from .errors import ConnectorError


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Empty(Input):
    pass


class DateRange(Input):
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def dates(self):
        days = (self.end_date - self.start_date).days
        if not 0 <= days < 31:
            raise ValueError("Use an ordered, inclusive date range of at most 31 days.")
        return self


class Activities(Input):
    start_date: date | None = None
    end_date: date | None = None
    activity_type: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]{0,63}$")
    offset: int = Field(default=0, ge=0, le=10000, strict=True)
    limit: int = Field(default=20, ge=1, le=50, strict=True)

    @model_validator(mode="after")
    def dates(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must not follow end_date")
        return self


class Activity(Input):
    activity_id: int = Field(gt=0, le=9223372036854775807, strict=True)


class HealthRange(DateRange):
    metric: Literal["weight", "steps", "stress", "sleep", "hrv", "body_battery", "daily_summary"]


class DayDetail(Input):
    date: date
    metric: Literal["sleep", "hrv", "heart_rate"]


# Structured fields only; arbitrary free-text labels are not anonymized.
PRIVATE_KEYS = {
    "latitude", "longitude", "lat", "lon", "lng", "startlatitude", "startlongitude",
    "endlatitude", "endlongitude", "positionlat", "positionlong", "positionlon",
    "startpositionlat", "startpositionlong", "endpositionlat", "endpositionlong",
    "gps", "coordinates", "polyline", "email", "emailaddress", "username",
    "displayname", "fullname", "firstname", "lastname", "address", "userprofilepk",
    "ownerid", "ownerprofilepk", "ownerfullname", "ownerdisplayname", "locationname",
    "access_token", "authorization", "apikey", "refreshtoken", "password",
}


def sanitize(value: object, depth: int = 0) -> object:
    if depth > 40:
        raise ConnectorError("Garmin response is too deeply nested.")
    if isinstance(value, dict):
        return {str(k): sanitize(v, depth + 1) for k, v in value.items()
                if str(k).lower().replace("_", "").replace("-", "") not in NORMALIZED_PRIVATE_KEYS}
    if isinstance(value, list):
        return [sanitize(v, depth + 1) for v in value]
    return value


NORMALIZED_PRIVATE_KEYS = {k.replace("_", "").replace("-", "") for k in PRIVATE_KEYS}


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    model: type[Input]

    def definition(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.model.model_json_schema(),
            "annotations": {"readOnlyHint": True, "destructiveHint": False,
                            "idempotentHint": True, "openWorldHint": True},
        }


TOOLS = (
    Tool("garmin_list_activities", "Read a page of Garmin activities. Use offset/limit for pagination; stop when fewer than limit records are returned. Dates use the account's calendar dates. activity_type is Garmin's type key (e.g. running, lap_swimming, strength_training), not an exercise name. No inferred fitness conclusions.", Activities),
    Tool("garmin_get_activity", "Read the original Garmin summary/details for an activity ID from garmin_list_activities. Preserve units, elapsed versus moving time, and session structure. Do not infer swimming continuity from average pace.", Activity),
    Tool("garmin_get_activity_workouts", "Read Garmin's workouts associated with an activity. Availability and schema vary: this is NOT a guarantee of executed sets, edited exercise names, reps or weights. Return only what the API supplies; do not invent missing strength records.", Activity),
    Tool("garmin_get_health_range", "Read weight (including BIA estimates if supplied), steps, stress, sleep summaries, HRV summaries, Body Battery, or daily summaries over at most 31 inclusive calendar days. Preserve original units; values are device estimates, not diagnoses or proof of muscle gain/loss.", HealthRange),
    Tool("garmin_get_day_detail", "Read original sleep, HRV or heart-rate data for one explicit calendar date. A missing measurement is not zero. HRV/heart rate alone cannot diagnose recovery or health.", DayDetail),
    Tool("garmin_connector_status", "Report connector capabilities and local date without contacting Garmin or revealing any key. This does not validate authentication or account coverage.", Empty),
)


class ToolService:
    def __init__(self, client: GarminClient) -> None:
        self.client = client
        self._gate = asyncio.Semaphore(4)

    def definitions(self) -> list[dict]:
        return [tool.definition() for tool in TOOLS]

    async def call(self, name: str, arguments: dict) -> dict:
        tool = next((t for t in TOOLS if t.name == name), None)
        if tool is None:
            raise KeyError(name)
        parsed = tool.model.model_validate(arguments)
        async with self._gate:
            try:
                async with asyncio.timeout(45):
                    result = await self._execute(name, parsed)
            except TimeoutError:
                raise ConnectorError("Garmin request timed out. Try a smaller request later.") from None
        output = {
            "source": "Garmin Connect Personal API",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "timezone": self.client.settings.timezone,
            "data": sanitize(result),
            "notes": [
                "Original values and units; no assumptions about missing measurements.",
                "Coordinate/profile fields filtered; activity titles and notes can still identify you.",
                "Device/body-composition estimates do not establish medical status or muscle gain.",
            ],
        }
        if name == "garmin_get_activity_workouts":
            output["notes"].append("Associated workout data may not contain executed or manually corrected strength sets; FIT decoding is not implemented in this version.")
        if len(json.dumps(output, ensure_ascii=False, allow_nan=False).encode()) > 512 * 1024:
            raise ConnectorError("Result too large for the connector. Use a shorter range or lower limit.")
        return output

    async def _execute(self, name: str, args: Input) -> object:
        if name == "garmin_connector_status":
            return {"version": "0.1.0", "read_only": True, "garmin_authenticated": "not_checked",
                    "today": datetime.now(ZoneInfo(self.client.settings.timezone)).date().isoformat(),
                    "tools": [t.name for t in TOOLS], "fit_decoding": False}
        if isinstance(args, Activities):
            params = {"start": args.offset, "limit": args.limit}
            for field, remote in (("start_date", "startDate"), ("end_date", "endDate"), ("activity_type", "activityType")):
                value = getattr(args, field)
                if value is not None:
                    params[remote] = value.isoformat() if isinstance(value, date) else value
            return await self.client.get("/activitylist-service/activities/search/activities", params)
        if isinstance(args, Activity):
            path = f"/activity-service/activity/{args.activity_id}"
            if name == "garmin_get_activity_workouts":
                path += "/workouts"
            return await self.client.get(path)
        if isinstance(args, HealthRange):
            start, end = args.start_date.isoformat(), args.end_date.isoformat()
            paths = {
                "weight": (f"/weight-service/weight/range/{start}/{end}", {"includeAll": "true"}),
                "steps": (f"/usersummary-service/stats/steps/daily/{start}/{end}", None),
                "stress": (f"/usersummary-service/stats/stress/daily/{start}/{end}", None),
                "hrv": (f"/hrv-service/hrv/daily/{start}/{end}", None),
                "sleep": ("/sleep-service/sleep/dailySleepSummariesByDate", {"startDate": start, "endDate": end}),
                "body_battery": ("/wellness-service/wellness/bodyBattery/reports/daily", {"startDate": start, "endDate": end}),
                "daily_summary": ("/usersummary-service/v2/dailysummaries", {"startDate": start, "endDate": end}),
            }
            path, params = paths[args.metric]
            return await self.client.get(path, params)
        if isinstance(args, DayDetail):
            day = args.date.isoformat()
            paths = {
                "sleep": ("/sleep-service/sleep/dailySleep", {"date": day}),
                "hrv": (f"/hrv-service/hrv/{day}", None),
                "heart_rate": ("/wellness-service/wellness/dailyHeartRate", {"date": day}),
            }
            path, params = paths[args.metric]
            return await self.client.get(path, params)
        raise ConnectorError("Unsupported operation.")
