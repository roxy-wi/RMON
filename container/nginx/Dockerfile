FROM nginx:stable-alpine
RUN apk add --no-cache python3 openssl
COPY default.conf.template runtime.py /opt/rmon-proxy/
RUN ln -s /etc/ssl/certs/rmon/rmon.crt /etc/ssl/certs/rmon.crt \
    && ln -s /etc/ssl/certs/rmon/rmon.key /etc/ssl/certs/rmon.key
ENTRYPOINT ["python3", "/opt/rmon-proxy/runtime.py"]
EXPOSE 8080
