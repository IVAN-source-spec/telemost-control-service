from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError


class AwsEc2ControlError(RuntimeError):
    pass


class AwsEc2Controller:
    def __init__(
        self,
        *,
        enabled: bool,
        region: str,
        instance_id: str,
        machine_id: str,
        client: Any | None = None,
    ) -> None:
        self.enabled = enabled
        self.region = region
        self.instance_id = instance_id
        self.machine_id = machine_id
        self._client = client
        self._lock = threading.Lock()

    @classmethod
    def from_env(cls) -> "AwsEc2Controller":
        enabled = os.getenv("AWS_EC2_CONTROL_ENABLED", "0").strip().lower() in {
            "1", "true", "yes", "on"
        }
        return cls(
            enabled=enabled,
            region=os.getenv("AWS_REGION", "eu-central-1").strip(),
            instance_id=os.getenv("AWS_EC2_INSTANCE_ID", "").strip(),
            machine_id=os.getenv("AWS_EC2_MACHINE_ID", "telemost-aws-1").strip(),
        )

    @property
    def configured(self) -> bool:
        return bool(self.enabled and self.region and self.instance_id and self.machine_id)

    def _ec2(self):
        if not self.configured:
            raise AwsEc2ControlError("Управление AWS EC2 не настроено")
        if self._client is None:
            self._client = boto3.Session().client("ec2", region_name=self.region)
        return self._client

    def _call(self, operation: str, **kwargs):
        try:
            return getattr(self._ec2(), operation)(**kwargs)
        except (BotoCoreError, ClientError) as error:
            code = ""
            if isinstance(error, ClientError):
                code = str(error.response.get("Error", {}).get("Code") or "")
            safe = code or error.__class__.__name__
            raise AwsEc2ControlError(f"AWS EC2 вернул ошибку: {safe}") from error

    def status(self) -> dict[str, Any]:
        if not self.configured:
            return {
                "configured": False,
                "machine_id": self.machine_id,
                "ec2_state": "not_configured",
            }
        response = self._call("describe_instances", InstanceIds=[self.instance_id])
        reservations = response.get("Reservations") or []
        instances = [item for reservation in reservations for item in reservation.get("Instances", [])]
        if len(instances) != 1:
            raise AwsEc2ControlError("AWS EC2 не вернул настроенный инстанс")
        instance = instances[0]
        state = str((instance.get("State") or {}).get("Name") or "unknown")
        return {
            "configured": True,
            "machine_id": self.machine_id,
            "instance_id": self.instance_id,
            "region": self.region,
            "ec2_state": state,
            "public_ip": instance.get("PublicIpAddress"),
            "private_ip": instance.get("PrivateIpAddress"),
            "instance_type": instance.get("InstanceType"),
            "launched_at": instance.get("LaunchTime").isoformat()
            if instance.get("LaunchTime")
            else None,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    def start(self) -> dict[str, Any]:
        with self._lock:
            current = self.status()
            if current["ec2_state"] in {"running", "pending"}:
                return {**current, "changed": False}
            response = self._call("start_instances", InstanceIds=[self.instance_id])
            change = (response.get("StartingInstances") or [{}])[0]
            return {
                **current,
                "changed": True,
                "ec2_state": str((change.get("CurrentState") or {}).get("Name") or "pending"),
            }

    def stop(self) -> dict[str, Any]:
        with self._lock:
            current = self.status()
            if current["ec2_state"] in {"stopped", "stopping"}:
                return {**current, "changed": False}
            response = self._call("stop_instances", InstanceIds=[self.instance_id])
            change = (response.get("StoppingInstances") or [{}])[0]
            return {
                **current,
                "changed": True,
                "ec2_state": str((change.get("CurrentState") or {}).get("Name") or "stopping"),
            }
