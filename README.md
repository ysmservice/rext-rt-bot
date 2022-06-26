![Python](https://img.shields.io/badge/Python-3.10-blue?logo=Python&logoColor=white) [![LICENSE](https://img.shields.io/badge/license-BSD%204--Clause-blue)](https://github.com/RextTeam/rt-bot/blob/main/LICENSE) [![Discord Bots](https://top.gg/api/widget/servers/716496407212589087.svg)](https://top.gg/bot/716496407212589087) [![Discord Bots](https://top.gg/api/widget/upvotes/716496407212589087.svg)](https://top.gg/bot/716496407212589087) [![Discord](https://img.shields.io/discord/718641964672876614?label=support&logo=discord)](https://discord.gg/ugMGw5w)
# rt-bot
It's a Discord Bot that has a lot of features, including unique and useful features, in addition to most Bots.
<details><summary>日本語</summary><div>

## 日本語版 README
RTのBotで、メインプログラムです。  
ほとんどの処理がこれで行われます。  
現在プログラムを書き直し中で、現行のRTは[この旧リポジトリ](https://github.com/RT-Team/rt-bot)にあるプログラムで動いています。

### 要件
* Python 3.10以上
* MySQL/MariaDB
* `requirements.txt`にあるPython用ライブラリ全て

### 用意
1. 要件にあるものをまずインストールします。
2. `data.json.template`と`secret.json.template`のコピーを作って、名前をそれぞれ`.template`を消した名前にします。
3. `data.json`と`secret.json`の中身をそこに書かれてる通りに適切なものを書き込みます。
4. リポジトリ`rt-lib`を`clone`してフォルダの名前を`rtlib`にする。
5. バックエンドを用意する(必須ではない)。詳細は[バックエンド](https://github.com/RextTeam/rt-backend)のリポジトリを見てください。
6. ルートに`secret.key`を`rtlib/rtlib/common/make_key.py`で作る。もしバックエンドも起動するのならそれをバックエンド側にもコピーする。

あなたは上記のセットアップを`build.sh`を実行することによってすることができます。

### 起動方法
`python3 main.py test`で起動が可能です。  
本番時は`test`を`production`にしてください。  
もし、バックエンドの起動で引数に`canary`を入れてる場合は、こちらでも`canary`を入れてください。  
テスト時の場合はシャードを使用しませんが、もしテストモードでシャードを使用したい場合は、引数に追加で`shard`を入れてください。
</div></details>
<details><summary>English</summary><div>

## English version README
This is the main program of RT Discord Bot.  
Most features were provided by this program.  
The program is currently being rewritten and the current RT is working with the program in [this old repository](https://github.com/RT-Team/rt-bot).

### Requirements
* Python 3.10
* MySQL / MariaDB
* All libraries for Python in `requirements.txt`.
* Others (optional)
  * `cogs/tts/readme.md`

### Preparation
1. Setup above Requirements.
2. Make copies of `data.json.template` and `secret.json.template` and name them with `.template` removed respectively.
3. Write the appropriate contents of `data.json` and `secret.json` as written there.
4. Clone the repository `rt-lib` and name the folder `rtlib`.
5. Provide a backend (not required). See the [backend of RT](https://github.com/RextTeam/rt-backend) repository for details.
6. Create `secret.key` in the root with `rtlib/rtlib/common/make_key.py`. Copy it to the backend side if the backend is also started.

You can run the above process by running `build.sh`.

### How to run
Command: `python3 main.py [test|canary|production]` or `python3 test.py ... shard`  
Set `test` for test mode and `production` for production.  
If you put `canary` in the argument when you start the backend, please put `canary` here as well.  
If you do not use shard in test mode, but you want to use shard in test mode, please put `shard` in the argument additionally.
</div></details>
