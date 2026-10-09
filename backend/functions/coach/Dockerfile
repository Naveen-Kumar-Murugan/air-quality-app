FROM public.ecr.aws/lambda/python:3.12

# Install dependencies
RUN pip install strands-agents httpx boto3

# Copy common layer from the coach directory
COPY common /var/task/common

# Copy function code
COPY app.py /var/task/app.py

# Set the handler
CMD ["app.lambda_handler"]
