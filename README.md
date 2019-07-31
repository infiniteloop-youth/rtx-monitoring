# rtx-monitoring

YAMAHA RTXシリーズをモニタリングします。

Forked from https://github.com/mi2428/rtx1200-network-visualization

## 使っている技術

- Docker
- Docker Compose
- Python
- Telnet(telnetlib)
- SSH(paramiko)
- Lua
- InfluxDB
- Grafana

## 使い方

1. docker-compose.ymlの環境変数を編集する(パスワードなど)
2. `docker-compose up --build -d`する
3. `localhost:3000`に行く
4. `RTX Resource Monitor(lua/ssh).json`をインポートする

## 既知の問題

`grafana`のパーミッションがおかしい→`sudo chown 472 -R grafana`してください(コンテナの再起動が必要)

## 更新

```sh
docker-compose stop
docker-compose rm
sudo chown $(whoami) -R grafana influxdb
git pull
docker-compose build
sudo chown 472 -R grafana
sudo chown root -R influxdb
docker-compose up -d
```

## ライセンス

フォーク元と同様、Unlicense として公開します。
このソフトウェアは株式会社インフィニットループでの業務内において、https://github.com/mi2428 さんのフォーク元コード ( https://github.com/mi2428/rtx1200-network-visualization )を修正する形で作成されました。
