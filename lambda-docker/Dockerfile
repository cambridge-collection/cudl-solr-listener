FROM public.ecr.aws/lambda/provided:al2

ARG TARGETARCH

RUN yum install -y curl jq unzip

COPY bootstrap ${LAMBDA_RUNTIME_DIR}
RUN chmod 755 ${LAMBDA_RUNTIME_DIR}/bootstrap

COPY ./*.sh ${LAMBDA_TASK_ROOT}

RUN chmod a+x ${LAMBDA_TASK_ROOT}/*.sh

RUN ${LAMBDA_TASK_ROOT}/install-awscli-${TARGETARCH}.sh

CMD [ "aws.sh.handler" ]
