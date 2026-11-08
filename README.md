# Squeezelite Android (Fork)

Android 8.1 (API 27) 対応版 Squeezelite

## 公開リポジトリ

- 公開source（履歴なしsnapshot）: https://github.com/hogehonya/squeezelite-android
  - [CDrummond/squeezelite](https://github.com/CDrummond/squeezelite) の fork。`main` はレビュー済みsourceの履歴なしsnapshotです。
- 開発履歴は Gitea `honya-dev-forks/squeezelite-android` で管理しています。公開snapshotには履歴を含めません。

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

## 現在の試用ビルド

- versionName 0.6.1 / versionCode 601、minSdk 27 / targetSdk 34、armeabi-v7a / arm64-v8a
- 署名はAndroid Debug署名の試用版です。リリース署名・長期配布用の版は未整備です。
- 試用APK SHA256: `ea2ec404df3e88ae5c0fcfa8cb4a83954dd06d22c9e69b6b72cd5773525c35b0`（8,058,725 bytes）
- 配布時は、APKに対応するcommitの公開snapshot（`main`）と通知文を併せて配布します。

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

2026-11-08時点。

| 端末 | OS | ABI | 状態 |
|------|----|-----|------|
| Lenovo ThinkSmart View (CD-18781Y) `.60` / `.61` / `.62` | LineageOS 15.1（Android 8.1 / API 27） | armeabi-v7a | 0.6.1/601（2026-03ビルド）導入済み。Lyrion接続・再生を確認 |
| Pixel 7 | Android 17 / API 37 | arm64-v8a | 0.6.1/601（2026-11-04ビルド）上書き導入・起動。Lyrion検出/接続、AAudio 44.1kHz/2chの非無音出力を確認（聴感は未確認） |
| arrows F-52G | Android 16（API 36） | arm64-v8a | 0.6.1/601（2026-11-08）上書き導入。起動・再生は未確認 |
| arrows F-52E | Android 16（API 36） | arm64-v8a | 0.6.1/601（2026-11-08）上書き導入。起動・再生は未確認 |

### 既知の制約

- Pixel 7（4096byte page）で `libsqueezelite.so` の16KB page非整合の互換性警告を確認しました。16KB page端末での動作は未検証です。
- 試用APKはAndroid Debug署名です。署名の異なるAPKへの上書き更新はできません。
- ThinkSmart Viewの導入済みAPKは2026-03ビルドで、現行APKとは同一version・同一署名ですがバイナリは異なります（ビルド環境差。クラス/メソッド構成とネイティブシンボルは同一）。

## ライセンス

GPL-3.0 (upstream準拠)

## upstream

- https://github.com/CDrummond/squeezelite
- https://f-droid.org/en/packages/org.lyrion.squeezelite/
