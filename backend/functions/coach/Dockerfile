FROM public.ecr.aws/lambda/python:3.12

# Install dependencies
RUN pip install strands-agents httpx boto3

# Copy common layer
COPY backend/layers/common/common /var/task/common

# Copy function code
COPY backend/functions/coach/app.py /var/task/app.py

# Set the handler
CMD ["app.lambda_handler"]
