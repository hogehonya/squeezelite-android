# Squeezelite Android (Fork)

Android 8.1 (API 27) 対応版 Squeezelite

## 変更点

[upstream](https://github.com/CDrummond/squeezelite) からの変更:

- API 27デバイスでの設定画面クラッシュ修正
- API 27デバイスでのネイティブライブラリ読み込み修正
- API 26-28でのフォアグラウンドサービスANR修正

### 修正ファイル

| ファイル | 修正内容 |
|----------|----------|
| `Utils.java` | BtDevice名nullチェック追加 |
| `SettingsActivity.java` | BluetoothAdapter nullチェック追加 |
| `squeezelite.h` | API 27向けmutex_create_p修正 |
| `pa_aaudio.c` | AAudio API 28関数をコンパイル時条件分岐 |
| `toolchain.py` | ネイティブライブラリAPIレベル28→27 |
| `PlayerService.java` | API 26-28でstartForeground()呼び出し |

## ビルド

### 必要環境

- Java 17
- Android SDK (API 34)
- Android NDK (27.2.12479018)
- CMake (3.22.1)
- meson, ninja

### ビルド手順

```bash
cd android
./gradlew assembleDebug
```

APK出力: `app/build/outputs/apk/debug/app-debug.apk`

## 公開用source snapshot

公開用のsource snapshotは、APKに対応するcommitを指定して作成します。

```bash
python3 tools/export_public_source.py \
  --ref <FULL_COMMIT_SHA> \
  --output /absolute/path/source.tar.gz
```

snapshotはGitの履歴を含めず、診断用bugreport、ローカル設定、鍵、生成物を除外します。収録commit、各ファイルのSHA256、除外一覧はアーカイブ内の `PUBLIC_SOURCE_MANIFEST.json` に記録されます。

既存のGit履歴は削除・書換されず、元のcloneやホストに残ります。このsnapshotには履歴を含めません。

APKを配布するときは、対応するsource snapshotと通知文を同時に配布します。現在のAPKはdebug試用版（versionCode 601）です。同じ署名による更新は通常の上書き更新として扱えますが、新しい署名鍵で署名したAPKへは通常の上書き更新ができません。

## 動作確認デバイス

- Lenovo ThinkSmart View (CD-18781Y)
  - LineageOS 15.1 (Android 8.1 / API 27)
  - armeabi-v7a

## ライセンス

GPL-3.0 (upstream準拠)

## upstream

- https://github.com/CDrummond/squeezelite
- https://f-droid.org/en/packages/org.lyrion.squeezelite/
