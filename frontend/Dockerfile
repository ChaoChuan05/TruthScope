FROM nginx:alpine AS runtime

RUN rm -f /etc/nginx/conf.d/default.conf \
    && mkdir -p /opt/truthscope \
    && chown -R nginx:nginx /opt/truthscope /usr/share/nginx/html

COPY nginx.conf /etc/nginx/nginx.conf
COPY --chown=nginx:nginx index.html style.css script.js login-wave.js oauth-test.html \
    /usr/share/nginx/html/
COPY --chown=nginx:nginx config.template.js /opt/truthscope/config.template.js
COPY --chmod=755 docker-entrypoint.d/40-truthscope-config.sh \
    /docker-entrypoint.d/40-truthscope-config.sh

USER nginx

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/healthz"]

STOPSIGNAL SIGQUIT

CMD ["nginx", "-g", "daemon off;"]
