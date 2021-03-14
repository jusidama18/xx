file="trackers.txt"
echo "$(curl -Ns https://trackerslist.com/best_aria2.txt | awk '$1' | tr ',' '\n')" > trackers.txt
echo "$(curl -Ns https://raw.githubusercontent.com/ngosang/trackerslist/master/trackers_all.txt)" >> trackers.txt
tmp=$(sort trackers.txt | uniq) && echo "$tmp" > trackers.txt
sed -i '/^$/d' trackers.txt
sed -z -i 's/\n/,/g' trackers.txt
tracker_list=$(cat trackers.txt)
if [ -f $file ] ; then
    rm $file
fi
tracker="[$tracker_list]"
export MAX_DOWNLOAD_SPEED=0
export MAX_CONCURRENT_DOWNLOADS=5
aria2c --enable-rpc --rpc-listen-all=false --rpc-listen-port 6800 --check-certificate=false\
   --max-connection-per-server=10 --rpc-max-request-size=1024M \
   --bt-tracker="[$tracker_list]" --bt-max-peers=0 --seed-time=0.01 --min-split-size=10M \
   --follow-torrent=mem --split=10 \
   --daemon=true --allow-overwrite=true --max-overall-download-limit=$MAX_DOWNLOAD_SPEED --bt-stop-timeout=300 \
   --max-overall-upload-limit=1K --max-concurrent-downloads=$MAX_CONCURRENT_DOWNLOADS \
   --peer-id-prefix=-qB4220- --user-agent=qBittorrent/4.2.2 \
   --disk-cache=64M --file-allocation=prealloc --continue=true \
   --max-file-not-found=5 --max-tries=20 --auto-file-renaming=true \
   --bt-enable-lpd=true --seed-time=0.01 --seed-ratio=1.0 \
   --bt-force-encryption=true --bt-require-crypto=true --bt-min-crypto-level=arc4 \
   --content-disposition-default-utf8=true --http-accept-gzip=true --reuse-uri=true
