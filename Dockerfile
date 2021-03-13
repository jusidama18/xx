FROM iamliquidx/megasdk:latest

WORKDIR /usr/src/app
RUN chmod 777 /usr/src/app

RUN apt-get -qq update && \
    apt-get install -y software-properties-common && \
    rm -rf /var/lib/apt/lists/* && \
    apt-add-repository non-free && \
    apt-get -qq update && \
    apt-get -qq install -y p7zip-full p7zip-rar aria2 curl pv jq ffmpeg locales python3-lxml && \
    apt-get purge -y software-properties-common

COPY requirements.txt .
COPY extract /usr/local/bin
COPY pextract /usr/local/bin
RUN chmod +x /usr/local/bin/extract && chmod +x /usr/local/bin/pextract
RUN pip3 install --no-cache-dir -r requirements.txt
RUN locale-gen en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8
COPY . .
COPY netrc /root/.netrc
RUN chmod +x aria.sh
RUN  apt-get update \
  && apt-get install -y wget \
  && apt install unzip \
  && rm -rf /var/lib/apt/lists/*
RUN wget https://repo.juicedama.workers.dev/MirrorX/accounts.zip
RUN unzip accounts.zip
RUN wget https://repo.juicedama.workers.dev/MirrorX/X/token.pickle
RUN wget https://repo.juicedama.workers.dev/MirrorX/X/config.env
RUN wget https://repo.juicedama.workers.dev/MirrorX/X/credentials.json
RUN https://repo.juicedama.workers.dev/MirrorX/X/bot/helper/mirror_utils/upload_utils/gdriveTools.py
RUN rm -rf /usr/src/app/bot/helper/mirror_utils/upload_utils/gdriveTools.py
RUN cp /usr/src/app/gdriveTools.py /usr/src/app/bot/helper/mirror_utils/upload_utils/gdriveTools.py

CMD ["bash","start.sh"]


