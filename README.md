# Skylens — Air Quality Platform

Snap a photo of the sky, get an AQI estimate, and see it on a live map with
cleaner-route suggestions and an AI Air Coach. Built for the AWS hackathon.

**What it is:** a Flutter app (Android / iOS / Web) backed by a serverless AWS
stack — API Gateway + Lambda + DynamoDB + S3, a SageMaker sky-classifier model,
and a Bedrock-powered coach. Map data is seeded for Bengaluru; scan estimates
are estimates, not measurements.

**Live demo:** `https://<amplify-domain>` — landing page with a phone mockup
running the real backend (demo mode: bundled sample skies, no camera/GPS prompts).

## Architecture

```
Flutter app ──HTTPS + Cognito JWT──▶ API Gateway (HTTP API, JWT auth)
Amplify Hosting: landing page + phone mockup (Flutter web build in /app/)
Lambdas: upload-url │ scan │ scans-mine │ map │ route │ coach
S3 (scan images + model artifacts) │ SageMaker serverless endpoint │ Bedrock (coach)
DynamoDB: scans, geo-cells, stations, rate limits
External: OpenAQ/CPCB stations, Mapbox/OSRM routing
```

See `docs/02_architecture.md` for the full diagram and component details.

## How to run

### Backend (SAM)

```bash
cd backend
sam build
sam deploy --guided   # first time; afterwards: sam deploy
# Optional parameters:
#   --parameter-overrides 'WebAppOrigins=https://<amplify-domain>,http://localhost:*
#     HourlyScanLimit=100 SageMakerEndpointName=aq-sky-classifier MapboxToken=<token>'
```

### Seed demo data (Bengaluru)

```bash
cd backend
python scripts/seed_bangalore.py --local          # DynamoDB Local
python scripts/seed_bangalore.py                  # AWS tables
python scripts/reset_demo_data.py --local --reseed  # clean slate + reseed
```

### Flutter app

```bash
cd app
flutter pub get
flutter run --dart-define=API_BASE=http://127.0.0.1:3000 \
  --dart-define=USER_POOL_ID=<pool-id> --dart-define=CLIENT_ID=<client-id> \
  --dart-define=REGION=ap-south-1
```

### Web demo build (for the landing-page phone mockup)

```bash
cd app
flutter build web --release --base-href /app/ \
  --dart-define=API_BASE=https://<api-id>.execute-api.<region>.amazonaws.com \
  --dart-define=USER_POOL_ID=<pool-id> --dart-define=CLIENT_ID=<client-id> \
  --dart-define=REGION=<region> --dart-define=DEMO=true
cp -r build/web ../web/app/
```

### Warm up before the demo

```bash
python backend/scripts/warm_demo.py --api-base https://<api-id>.execute-api.<region>.amazonaws.com \
  --token <cognito-id-token> --image app/assets/demo/clear.jpg
```

Run 10 minutes before the demo, and again just before going on stage.

## Environment variables

| Name | Where | Purpose |
| ---- | ----- | ------- |
| `API_BASE` | Flutter `--dart-define` | HTTP API base URL |
| `USER_POOL_ID` / `CLIENT_ID` / `REGION` | Flutter `--dart-define` | Cognito auth config |
| `DEMO` | Flutter `--dart-define` | `true` enables demo mode (sample skies, fixed location) |
| `WebAppOrigins` | SAM parameter | Browser origins allowed by API + S3 CORS |
| `HourlyScanLimit` | SAM parameter | Max scans per user per hour (raise for demo) |
| `MapboxToken` | SAM parameter | Directions API token for routing |
| `SageMakerEndpointName` | SAM parameter | Sky-classifier endpoint name |

## Docs

Phase plans and references live in `docs/` — including the five phase files,
`02_architecture.md`, `03_data_modelling_and_geohash.md`, and model eval notes.

## Honest limitations

- Scan results are model estimates from a single photo, not calibrated measurements.
- Station coverage is limited to seeded Bengaluru zones; elsewhere the map is sparse.
- The classifier degrades on night, indoor, or heavily filtered photos.

## After the hackathon (cost hygiene)

Delete the SageMaker endpoint and model, remove training artifacts, empty the S3
buckets, then `sam delete`. Keep the Amplify site only if the landing page should
stay online.
