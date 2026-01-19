FROM public.ecr.aws/lambda/python:3.13

# Copy the requirements file and install dependencies.
COPY requirements.txt  ./
RUN pip install -r requirements.txt

# Copy your Lambda function code.
COPY app.py  ./

# Set the CMD to your Lambda handler (filename.function_name).
CMD [ "app.lambda_handler" ]
