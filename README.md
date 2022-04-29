# rt-bot
RTのBotで、メインプログラムです。  
ほとんどの処理がこれで行われます。

## 要件
* Python 3.10以上
* MySQL/MariaDB
* `requirements.txt`にあるPytohn用ライブラリ全て

## 用意
1. 要件にあるものをまずインストールします。
2. `data.json.template`と`secret.json.template`のコピーを作って、名前をそれぞれ`.template`を消した名前にします。
3. `data.json`と`secret.json`の中身をそこに書かれてる通りに適切なものを書き込みます。
4. リポジトリ`rt-lib`を`clone`してフォルダの名前を`rtlib`にする。

## 起動方法
`python3 main.py test`で起動が可能です。  
本番時は`test`を`production`にしてください。  
もし、バックエンドの起動で引数に`canary`を入れてる場合は、こちらでも`canary`を入れてください。  