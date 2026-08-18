# StudyFlow custom BgUtils POT provider
#
# Pinned to upstream PR #247 commit 411d8d6, which replaces axios inside
# BotGuard fetches with node:https to avoid protocol corruption under jsdom
# when a proxy is supplied by yt-dlp.
FROM node:22-bookworm

ARG BGUTIL_REPO=https://github.com/liuzhao1225/bgutil-ytdlp-pot-provider.git
ARG BGUTIL_COMMIT=411d8d6d04a6bcb00108fd16165d2aae213d08a6

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates git python3 make g++ \
       libcairo2-dev libpango1.0-dev libjpeg-dev libgif-dev librsvg2-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt
RUN git clone "$BGUTIL_REPO" bgutil-ytdlp-pot-provider \
    && cd bgutil-ytdlp-pot-provider \
    && git checkout "$BGUTIL_COMMIT"

WORKDIR /opt/bgutil-ytdlp-pot-provider/server
RUN npm ci \
    && npx tsc \
    && npm cache clean --force

EXPOSE 4416
CMD ["node", "build/main.js", "--port", "4416"]
