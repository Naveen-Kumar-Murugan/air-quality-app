# Step 1 Implementation: Infrastructure

## What Was Created

### `.gitignore`
Excludes `.aws-sam/`, `.env`, `*.pem`, `*.key`, `.DS_Store`, and `samconfig.toml` from version control.

### `template.yaml`
Complete AWS SAM template defining:
- **4 DynamoDB tables** (PAY_PER_REQUEST, TTL enabled): `GeoCellsTable`, `ScansTable` (with GSI `gsi1`), `StationsTable`, `RateLimitsTable`
- **2 S3 buckets**: `ScansBucket` (CORS for PUT, 30-day expiry), `ModelsBucket`
- **Cognito**: `UserPool` (email username, relaxed password policy, pre-signup trigger), `UserPoolClient` (USER_PASSWORD_AUTH, SRP, refresh token)
- **API Gateway**: `HttpApi` with CORS and `CognitoAuthorizer` (JWT)
- **Lambda Layer**: `CommonLayer` (python3.12)
- **Lambda Functions**: `HelloFunction` (GET /me, JWT-protected), `PreSignupFunction` (auto-confirms users)
- **Permission**: `PreSignupPermission` for Cognito to invoke the pre-signup trigger
- **Outputs**: `ApiUrl`, `UserPoolId`, `UserPoolClientId`, `Region`

### `functions/hello/app.py`
Stub Lambda that extracts the `sub` claim from the JWT authorizer context and returns it as JSON. Used to verify auth is working.

### `functions/pre_signup/app.py`
Cognito pre-signup trigger that auto-confirms guest users without email verification.

### `layers/common/python/common/__init__.py`
Empty init file for the shared common layer package. Will be populated with `geohash`, `aqi`, `cells`, and `util` modules in Step 2.

### `docs/SETUP.md`
Placeholder documentation for region selection, Bedrock model access, SageMaker quota, API keys, and SAM deployment outputs.

## Deployment
Skipped per instructions. Run `sam build && sam deploy --guided` when ready.
