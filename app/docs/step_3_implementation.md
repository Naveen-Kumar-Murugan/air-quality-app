# Step 3: Flutter Auth Flow Implementation

## Overview

Phase 1, Step 3 sets up the Flutter mobile app with guest authentication via Amazon Cognito and a basic app scaffold with 4-tab navigation.

## Files Created

| File | Purpose |
|------|---------|
| `pubspec.yaml` | Project metadata and dependencies |
| `lib/core/config.dart` | Runtime config via `--dart-define` (API_BASE, USER_POOL_ID, CLIENT_ID, REGION, DEMO) |
| `lib/features/auth/auth_service.dart` | Guest sign-up/sign-in using `amazon_cognito_identity_dart_2`, credentials stored in `flutter_secure_storage` |
| `lib/core/api_client.dart` | `dio` HTTP client with JWT interceptor that attaches the Cognito ID token to every request |
| `lib/main.dart` | App entry point with SplashScreen (auto guest sign-in) and HomeScreen (4-tab bottom nav) |
| `android/app/src/main/AndroidManifest.xml` | INTERNET, CAMERA, and LOCATION permissions |
| `ios/Runner/Info.plist` | Camera and location usage descriptions |
| `analysis_options.yaml` | Lint rules from `flutter_lints` |

## Dependencies

- **flutter_riverpod** — state management (wired in later phases)
- **dio** — HTTP client with interceptor support
- **flutter_secure_storage** — encrypted credential storage
- **amazon_cognito_identity_dart_2** — direct Cognito user pool operations (no Amplify overhead)
- **uuid** — generate unique guest usernames

## Configuration

Pass SAM output values at build time:

```bash
flutter run \
  --dart-define=API_BASE=https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com \
  --dart-define=USER_POOL_ID=us-east-1_xxxxxxxxx \
  --dart-define=CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx \
  --dart-define=REGION=us-east-1
```

Or edit the `defaultValue` fields in `lib/core/config.dart` directly for local development.

## Auth Flow

1. App launches → SplashScreen
2. Check `flutter_secure_storage` for existing guest credentials
3. If none: generate `guest_<uuid>` username + random password → Cognito `signUp` → store credentials
4. `authenticateUser` with stored credentials → receive ID token
5. Store ID token → call `GET /me` via ApiClient to verify
6. On success → navigate to HomeScreen with 4-tab bottom nav

## Next Steps

- Run `flutter pub get` once Flutter SDK is available
- Fill in actual SAM output values (userPoolId, clientId) from Step 1 deploy
- Proceed to Phase 2: Scan Pipeline
