package aicp.authz_test

import rego.v1

import data.aicp.authz

# 1. Demo application may access its approved model.
test_demo_local_allowed if {
    result := authz.decision with input as {
        "application_id": "demo-app",
        "model_id": "local-small",
    }

    result == {
        "allow": true,
        "reason": "ALLOW",
    }
}

# 2. Demo application cannot access restricted model.
test_demo_restricted_denied if {
    result := authz.decision with input as {
        "application_id": "demo-app",
        "model_id": "restricted-small",
    }

    result == {
        "allow": false,
        "reason": "MODEL_NOT_ALLOWED",
    }
}

# 3. Finance application may access restricted model.
test_finance_restricted_allowed if {
    result := authz.decision with input as {
        "application_id": "finance-assistant",
        "model_id": "restricted-small",
    }

    result == {
        "allow": true,
        "reason": "ALLOW",
    }
}

# 4. Finance application may access local model.
test_finance_local_allowed if {
    authz.allow with input as {
        "application_id": "finance-assistant",
        "model_id": "local-small",
    }
}

# 5. Test application may access local model.
test_test_app_local_allowed if {
    authz.allow with input as {
        "application_id": "test-app",
        "model_id": "local-small",
    }
}

# 6. Test application cannot access restricted model.
test_test_app_restricted_denied if {
    not authz.allow with input as {
        "application_id": "test-app",
        "model_id": "restricted-small",
    }
}

# 7. Unknown model is denied.
test_unknown_model_denied if {
    result := authz.decision with input as {
        "application_id": "demo-app",
        "model_id": "unknown-model",
    }

    result == {
        "allow": false,
        "reason": "MODEL_NOT_REGISTERED",
    }
}

# 8. Unknown application is denied.
test_unknown_application_denied if {
    result := authz.decision with input as {
        "application_id": "unregistered-app",
        "model_id": "local-small",
    }

    result == {
        "allow": false,
        "reason": "UNKNOWN_APPLICATION",
    }
}

# 9. Missing application identity is denied.
test_missing_application_denied if {
    result := authz.decision with input as {
        "model_id": "local-small",
    }

    result.allow == false
    result.reason == "UNKNOWN_APPLICATION"
}

# 10. Empty input is denied.
test_empty_input_denied if {
    result := authz.decision with input as {}

    result.allow == false
    result.reason == "MODEL_NOT_REGISTERED"
}