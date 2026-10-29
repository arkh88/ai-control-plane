package aicp.authz

import rego.v1

# Registered logical model identifiers.
registered_models := {
    "local-small",
    "restricted-small",
}

# Temporary static access policy.
# Later this configuration will be externalized.
application_models := {
    "demo-app": {"local-small"},
    "test-app": {"local-small"},
    "finance-assistant": {
        "local-small",
        "restricted-small",
    },
}

# Security rule: deny unless explicitly allowed.
default allow := false

allow if {
    registered_models[input.model_id]
    application_models[input.application_id][input.model_id]
}

# Default reason covers missing or unregistered models.
default reason := "MODEL_NOT_REGISTERED"

reason := "UNKNOWN_APPLICATION" if {
    registered_models[input.model_id]

    # Treat a missing application_id as an empty string.
    app_id := object.get(input, "application_id", "")

    # Unknown or missing applications are denied.
    not application_models[app_id]
}

reason := "MODEL_NOT_ALLOWED" if {
    registered_models[input.model_id]
    application_models[input.application_id]
    not application_models[input.application_id][input.model_id]
}

reason := "ALLOW" if {
    allow
}

# Version of the model-access policy contract.
policy_version := "model-access/v1"

decision := {
    "allow": allow,
    "reason": reason,
    "policy_version": policy_version,
}