from __future__ import annotations

import json
from pathlib import Path

from pydantic import Field

from lablinks_poc.models import ClaimManifest, ExecutionTemplate, Policy, StrictModel


class RuntimeTemplateConfig(StrictModel):
    template_id: str
    version: str
    local_dataset_ref: str
    metric_name: str
    units: str
    baseline_metric_value: float
    internal_adjustment: float
    external_adjustment: float


class LabNodeConfig(StrictModel):
    lab_id: str
    display_name: str
    node_endpoint: str
    default_policy_id: str
    claims: list[ClaimManifest] = Field(default_factory=list)
    policies: list[Policy] = Field(default_factory=list)
    execution_templates: list[ExecutionTemplate] = Field(default_factory=list)
    runtime_templates: list[RuntimeTemplateConfig] = Field(default_factory=list)

    def get_policy(self, policy_id: str) -> Policy:
        for policy in self.policies:
            if policy.policy_id == policy_id:
                return policy
        raise KeyError(policy_id)

    def get_runtime_template(self, template_id: str) -> RuntimeTemplateConfig:
        for template in self.runtime_templates:
            if template.template_id == template_id:
                return template
        raise KeyError(template_id)


def load_lab_node_config(path: str | Path) -> LabNodeConfig:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return LabNodeConfig.model_validate(payload)

