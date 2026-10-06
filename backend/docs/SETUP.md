# Setup

## AWS Region

- **Region:** us-east-1 (recommended; change as needed)

## Bedrock Model Access

- **Model:** Claude 3.5 Haiku (or Claude 3 Haiku as fallback)
- **Status:** Pending — request access via AWS Console → Amazon Bedrock → Model access

## SageMaker GPU Quota

- **Instance type:** ml.g4dn.xlarge for training job usage
- **Status:** Check via Service Quotas → Amazon SageMaker; request 1 instance if quota is zero

## API Keys

Store the following in a local `.env` file (gitignored):

- **OpenAQ:** Free tier key from https://openaq.org/
- **Mapbox:** Access token from https://account.mapbox.com/

## SAM Deployment Outputs

After running `sam deploy --guided`, record these values:

- **ApiUrl:** `<pending deploy>`
- **UserPoolId:** `<pending deploy>`
- **UserPoolClientId:** `<pending deploy>`
- **Region:** `<pending deploy>`
