import json
import shutil
import subprocess
from typing import Any


class AwsCliError(Exception):
    """Raised when AWS CLI execution fails in a user-actionable way."""

    def __init__(self, message: str, status_code: int = 500) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _ensure_aws_cli() -> None:
    if shutil.which("aws") is None:
        raise AwsCliError(
            "AWS CLI is not installed or is not available on PATH.",
            status_code=503,
        )


def _run_aws_command(args: list[str], expect_json: bool = True) -> Any:
    _ensure_aws_cli()

    try:
        result = subprocess.run(
            ["aws", *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        raise AwsCliError("AWS CLI command timed out.", status_code=504) from exc
    except OSError as exc:
        raise AwsCliError(f"Failed to run AWS CLI: {exc}", status_code=500) from exc

    if result.returncode != 0:
        error = (result.stderr or result.stdout).strip()
        raise AwsCliError(_friendly_aws_error(error), status_code=_status_for_error(error))

    output = result.stdout.strip()
    if not expect_json:
        return output

    if not output:
        return {}

    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        raise AwsCliError("AWS CLI returned invalid JSON output.", status_code=502) from exc


def _friendly_aws_error(error: str) -> str:
    lower_error = error.lower()

    if "unable to locate credentials" in lower_error or "could not find credentials" in lower_error:
        return "AWS CLI is not configured. Run `aws configure` and try again."

    if "you must specify a region" in lower_error:
        return "AWS region is missing. Provide a valid AWS region."

    if "invalid endpoint" in lower_error or "could not connect to the endpoint url" in lower_error:
        return "Invalid AWS region or endpoint for this request."

    if "expiredtoken" in lower_error:
        return "AWS credentials have expired. Refresh your credentials and try again."

    if "accessdenied" in lower_error or "unauthorizedoperation" in lower_error:
        return "AWS credentials do not have permission to scan these resources."

    return error or "AWS CLI command failed."


def _status_for_error(error: str) -> int:
    lower_error = error.lower()

    if "unable to locate credentials" in lower_error or "could not find credentials" in lower_error:
        return 401

    if "invalid endpoint" in lower_error or "could not connect to the endpoint url" in lower_error:
        return 400

    if "accessdenied" in lower_error or "unauthorizedoperation" in lower_error:
        return 403

    return 500


def list_regions() -> list[str]:
    output = _run_aws_command(
        ["ec2", "describe-regions", "--query", "Regions[].RegionName", "--output", "text"],
        expect_json=False,
    )
    return sorted(region for region in output.split() if region)


def get_tagged_resources(region: str) -> list[dict[str, Any]]:
    response = _run_aws_command(
        ["resourcegroupstaggingapi", "get-resources", "--region", region, "--output", "json"]
    )

    resources = []
    for mapping in response.get("ResourceTagMappingList", []):
        arn = mapping.get("ResourceARN", "")
        resources.append(
            {
                "resource_type": _resource_type_from_arn(arn),
                "arn": arn,
                "region": _region_from_arn(arn) or region,
                "tags": _normalize_tags(mapping.get("Tags", [])),
                "configuration": {},
            }
        )

    return resources


def get_ec2_instances(region: str) -> list[dict[str, Any]]:
    response = _run_aws_command(
        ["ec2", "describe-instances", "--region", region, "--output", "json"]
    )

    instances = []
    for reservation in response.get("Reservations", []):
        for instance in reservation.get("Instances", []):
            instance_id = instance.get("InstanceId")
            arn = (
                f"arn:aws:ec2:{region}:unknown:instance/{instance_id}"
                if instance_id
                else ""
            )
            instances.append(
                {
                    "resource_type": "ec2:instance",
                    "arn": arn,
                    "region": region,
                    "tags": _normalize_tags(instance.get("Tags", [])),
                    "configuration": {
                        "instance_id": instance_id,
                        "instance_type": instance.get("InstanceType"),
                        "state": instance.get("State", {}).get("Name"),
                        "launch_time": str(instance.get("LaunchTime")) if instance.get("LaunchTime") else None,
                        "availability_zone": instance.get("Placement", {}).get("AvailabilityZone"),
                    },
                }
            )

    return instances


def get_rds_instances(region: str) -> list[dict[str, Any]]:
    response = _run_aws_command(
        ["rds", "describe-db-instances", "--region", region, "--output", "json"]
    )

    instances = []
    for instance in response.get("DBInstances", []):
        instances.append(
            {
                "resource_type": "rds:db",
                "arn": instance.get("DBInstanceArn", ""),
                "region": region,
                "tags": {},
                "configuration": {
                    "db_instance_identifier": instance.get("DBInstanceIdentifier"),
                    "db_instance_class": instance.get("DBInstanceClass"),
                    "engine": instance.get("Engine"),
                    "status": instance.get("DBInstanceStatus"),
                    "allocated_storage": instance.get("AllocatedStorage"),
                    "multi_az": instance.get("MultiAZ"),
                },
            }
        )

    return instances


def list_s3_buckets() -> list[dict[str, Any]]:
    response = _run_aws_command(["s3api", "list-buckets", "--output", "json"])

    buckets = []
    for bucket in response.get("Buckets", []):
        name = bucket.get("Name")
        buckets.append(
            {
                "resource_type": "s3:bucket",
                "arn": f"arn:aws:s3:::{name}" if name else "",
                "region": "global",
                "tags": {},
                "configuration": {
                    "name": name,
                    "creation_date": str(bucket.get("CreationDate")) if bucket.get("CreationDate") else None,
                },
            }
        )

    return buckets


def scan_region(region: str) -> dict[str, Any]:
    tagged_resources = get_tagged_resources(region)
    resources_by_key = {_resource_key(resource): resource for resource in tagged_resources}
    errors = []

    for scanner in (get_ec2_instances, get_rds_instances):
        try:
            for resource in scanner(region):
                resources_by_key.setdefault(_resource_key(resource), resource)
        except AwsCliError as exc:
            errors.append({"scanner": scanner.__name__, "message": exc.message})

    try:
        for resource in list_s3_buckets():
            resources_by_key.setdefault(_resource_key(resource), resource)
    except AwsCliError as exc:
        errors.append({"scanner": "list_s3_buckets", "message": exc.message})

    return {
        "region": region,
        "resource_count": len(resources_by_key),
        "resources": list(resources_by_key.values()),
        "partial_errors": errors,
    }


def _resource_key(resource: dict[str, Any]) -> str:
    return resource.get("arn") or f"{resource.get('resource_type')}:{resource.get('configuration')}"


def _resource_type_from_arn(arn: str) -> str:
    parts = arn.split(":", 5)
    if len(parts) < 6:
        return "unknown"

    service = parts[2]
    resource = parts[5]
    resource_kind = resource.split("/", 1)[0].split(":", 1)[0]
    return f"{service}:{resource_kind}" if resource_kind else service


def _region_from_arn(arn: str) -> str | None:
    parts = arn.split(":")
    if len(parts) > 3 and parts[3]:
        return parts[3]
    return None


def _normalize_tags(tags: list[dict[str, str]]) -> dict[str, str]:
    return {
        tag.get("Key", ""): tag.get("Value", "")
        for tag in tags
        if tag.get("Key")
    }
