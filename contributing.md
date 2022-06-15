# RT Contributing Guide
## Coding
大体以下に従います。  
https://gist.github.com/tasuren/bf1fcce48f1e23a5c7e6abd503bdb3c1
## Commit Log / Pull Request Name
最初に何をしたかの英語を入れて、右に内容を書きます。  
一行90文字以内に収めて、簡潔に書いてください。  
### Example
* `fix: ...` 修正
  * `fix[typo]: ...` 誤字の修正のみ
  * `fix[doc]: ...` ドキュメンテーションの修正のみ
* `update: ...` 更新
  * `update[doc]: ...` ドキュメンテーションの更新のみ
* `improve: ...` 改善した場合 (大抵はupdateでも良い)
* `remove: ...` 削除
## SQL
コラム名はキャメルケースで書いてください。  
SQLの最後に`;`を置くのを忘れないでください。
## 新機能について
まずはIssueを作ってそこで「私が作る」と言ってください。  
そして、どのように作るかを言っておいた方がPull Requestで破壊的更新を要求される確率が下がります。  
なので一度相談した方が安全でしょう。
## 引数
もちろん、スネークケースです。`channelid`は`channel_id`のようにしてください。  
また、Discordオブジェクトを要求している引数のクセに`.id`属性しか使わないなどの場合は、IDを要求する引数にしてください。  
大きい値の移動を極力減らしてください。
