import { computed, ref } from "vue";

const htmlLang = { en: "en", zh: "zh-CN", ja: "ja" };

const en = {
  language: "Language", chooseLanguage: "Choose your language", chooseLanguageText: "Select the language to use in the dashboard.",
  home: "Home", profile: "Profile", apiKeys: "API Keys", admin: "Admin", superadmin: "Superadmin", signOut: "Sign out",
  identity: "Knowledge identity", profileTitle: "Profile", profileText: "Update the public details attached to your UMST account.",
  username: "Username", email: "Email", alias: "Alias", description: "Description", saveProfile: "Save profile", saved: "Profile saved.", authorityType: "Authority type",
  developer: "Developer access", apiTitle: "API Keys", apiText: "Regular keys provide rate-limited read access. Admins and superadmins may upgrade their own keys to unlimited master keys for ingestion and storage writes.",
  keyName: "Key name", keyNameRequired: "Please enter a key name.", createKey: "Create API key", newKey: "New key:", active: "Active", revoked: "Revoked", revoke: "Revoke",
  regularKey: "Regular key", masterKey: "Master key", requestsPerHour: "requests/hour", unlimitedMaster: "Unlimited read, knowledge submission, embedding, and storage-write access.",
  upgradeMaster: "Upgrade to master", upgradeMasterConfirm: "Upgrade this key to an unlimited master key? This cannot be undone from the dashboard.", masterUpgraded: "API key upgraded to master.",
  adminTitle: "Admin tools", adminText: "Search semantic projections in Qdrant and manage object storage. Arbitrary SQL is restricted to the superadmin page.",
  vectorSearch: "Semantic search", qdrantTitle: "Qdrant search", qdrantText: "Search by text when an embedding provider is configured, or paste a vector directly.",
  queryText: "Query text", queryTextPlaceholder: "What is this an example of?", queryVector: "Query vector (optional)", filtersJson: "Payload filters as JSON", resultLimit: "Result limit", searchQdrant: "Search Qdrant", invalidJson: "Invalid JSON",
  files: "Files", objectStorage: "Object Storage", storageText: "This interface is connected to SERVER=", refresh: "Refresh", up: "Up", newFolder: "New folder name", createFolder: "Create folder", newFile: "New text file", upload: "Upload file", download: "Download", delete: "Delete", emptyFolder: "This folder is empty.", filePath: "File path", fileContent: "Text content", saveFile: "Save file",
  storageLoaded: "Storage loaded.", storageFileLoaded: "File loaded.", storagePathRequired: "Please enter a file path.", storageSaved: "File saved.", folderNameRequired: "Please enter a folder name.", folderCreated: "Folder created.", fileUploaded: "File uploaded.", deleteConfirm: "Delete", deleted: "Deleted.", newFileReady: "Enter a path and content, then save.",
  superadminTitle: "Superadmin", superadminText: "Promote users to admin and perform unrestricted database administration.", userToPromote: "User", giveAdmin: "Give admin", adminGranted: "is now an admin.",
  superSql: "Database administration", superSqlTitle: "Arbitrary PostgreSQL", superSqlText: "This executes exactly the PostgreSQL supplied below. It is intentionally available only to superadmins.", sqlCode: "SQL code", runSql: "Run SQL"
};

const zh = {
  ...en,
  language: "语言", chooseLanguage: "选择语言", chooseLanguageText: "选择控制台使用的语言。",
  home: "首页", profile: "个人资料", apiKeys: "API 密钥", admin: "管理员", superadmin: "超级管理员", signOut: "退出登录",
  identity: "知识身份", profileTitle: "个人资料", profileText: "更新与你的 UMST 账户关联的公开信息。", username: "用户名", email: "邮箱", alias: "昵称", description: "简介", saveProfile: "保存资料", saved: "资料已保存。", authorityType: "权限类型",
  developer: "开发者访问", apiTitle: "API 密钥", apiText: "普通密钥提供限速读取。管理员和超级管理员可以将自己的密钥升级为不限速的主密钥，用于提交知识、嵌入和写入存储。",
  keyName: "密钥名称", keyNameRequired: "请输入密钥名称。", createKey: "创建 API 密钥", newKey: "新密钥：", active: "启用", revoked: "已撤销", revoke: "撤销", regularKey: "普通密钥", masterKey: "主密钥", requestsPerHour: "次请求/小时", unlimitedMaster: "不限速读取、知识提交、嵌入和存储写入。", upgradeMaster: "升级为主密钥", upgradeMasterConfirm: "将此密钥升级为不限速主密钥？控制台中无法撤销。", masterUpgraded: "API 密钥已升级为主密钥。",
  adminTitle: "管理员工具", adminText: "在 Qdrant 中搜索语义投影并管理对象存储。任意 SQL 仅限超级管理员页面。", vectorSearch: "语义搜索", qdrantTitle: "Qdrant 搜索", qdrantText: "配置嵌入提供商后可用文本搜索，也可以直接粘贴向量。", queryText: "查询文本", queryTextPlaceholder: "这是什么的例子？", queryVector: "查询向量（可选）", filtersJson: "JSON 载荷过滤器", resultLimit: "结果数量", searchQdrant: "搜索 Qdrant", invalidJson: "JSON 无效",
  files: "文件", objectStorage: "对象存储", storageText: "当前连接到 SERVER=", refresh: "刷新", up: "上一级", newFolder: "新文件夹名称", createFolder: "创建文件夹", newFile: "新建文本文件", upload: "上传文件", download: "下载", delete: "删除", emptyFolder: "这个文件夹是空的。", filePath: "文件路径", fileContent: "文本内容", saveFile: "保存文件", storageLoaded: "存储已加载。", storageFileLoaded: "文件已加载。", storagePathRequired: "请输入文件路径。", storageSaved: "文件已保存。", folderNameRequired: "请输入文件夹名称。", folderCreated: "文件夹已创建。", fileUploaded: "文件已上传。", deleteConfirm: "删除", deleted: "已删除。", newFileReady: "请输入路径和内容，然后保存。",
  superadminTitle: "超级管理员", superadminText: "将用户提升为管理员并执行不受限制的数据库管理。", userToPromote: "用户", giveAdmin: "授予管理员", adminGranted: "现在是管理员。", superSql: "数据库管理", superSqlTitle: "任意 PostgreSQL", superSqlText: "这里会执行你提供的 PostgreSQL，因此仅向超级管理员开放。", sqlCode: "SQL 代码", runSql: "运行 SQL"
};

const ja = {
  ...en,
  language: "言語", chooseLanguage: "言語を選択", chooseLanguageText: "ダッシュボードで使用する言語を選択します。",
  home: "ホーム", profile: "プロフィール", apiKeys: "APIキー", admin: "管理者", superadmin: "スーパー管理者", signOut: "ログアウト",
  identity: "知識アイデンティティ", profileTitle: "プロフィール", profileText: "UMST アカウントに紐づく公開情報を更新します。", username: "ユーザー名", email: "メール", alias: "別名", description: "説明", saveProfile: "保存", saved: "プロフィールを保存しました。", authorityType: "権限タイプ",
  developer: "開発者アクセス", apiTitle: "APIキー", apiText: "通常キーは制限付き読み取りアクセスを提供します。管理者とスーパー管理者は自分のキーを無制限のマスターキーへ昇格できます。",
  keyName: "キー名", keyNameRequired: "キー名を入力してください。", createKey: "APIキーを作成", newKey: "新しいキー：", active: "有効", revoked: "無効", revoke: "無効化", regularKey: "通常キー", masterKey: "マスターキー", requestsPerHour: "リクエスト/時", unlimitedMaster: "無制限の読み取り、知識送信、埋め込み、ストレージ書き込み。", upgradeMaster: "マスターへ昇格", upgradeMasterConfirm: "このキーを無制限のマスターキーへ昇格しますか？ダッシュボードから元に戻せません。", masterUpgraded: "APIキーをマスターへ昇格しました。",
  adminTitle: "管理者ツール", adminText: "Qdrant の意味投影を検索し、オブジェクトストレージを管理します。任意SQLはスーパー管理者ページ限定です。", vectorSearch: "意味検索", qdrantTitle: "Qdrant 検索", qdrantText: "埋め込みプロバイダー設定時はテキスト検索、またはベクトルを直接貼り付けできます。", queryText: "検索テキスト", queryTextPlaceholder: "これは何の例ですか？", queryVector: "検索ベクトル（任意）", filtersJson: "JSONペイロードフィルター", resultLimit: "結果数", searchQdrant: "Qdrantを検索", invalidJson: "JSONが無効です",
  files: "ファイル", objectStorage: "オブジェクトストレージ", storageText: "接続先 SERVER=", refresh: "更新", up: "上へ", newFolder: "新しいフォルダ名", createFolder: "フォルダ作成", newFile: "新しいテキスト", upload: "アップロード", download: "ダウンロード", delete: "削除", emptyFolder: "このフォルダは空です。", filePath: "ファイルパス", fileContent: "テキスト内容", saveFile: "保存", storageLoaded: "ストレージを読み込みました。", storageFileLoaded: "ファイルを読み込みました。", storagePathRequired: "ファイルパスを入力してください。", storageSaved: "保存しました。", folderNameRequired: "フォルダ名を入力してください。", folderCreated: "フォルダを作成しました。", fileUploaded: "アップロードしました。", deleteConfirm: "削除", deleted: "削除しました。", newFileReady: "パスと内容を入力して保存してください。",
  superadminTitle: "スーパー管理者", superadminText: "ユーザーを管理者へ昇格し、制限なしのデータベース管理を実行します。", userToPromote: "ユーザー", giveAdmin: "管理者にする", adminGranted: "は管理者になりました。", superSql: "データベース管理", superSqlTitle: "任意のPostgreSQL", superSqlText: "入力したPostgreSQLをそのまま実行するため、スーパー管理者だけが使用できます。", sqlCode: "SQLコード", runSql: "SQLを実行"
};

const text = { en, zh, ja };

export function useI18n() {
  const lang = ref(localStorage.getItem("language") || "en");
  const t = computed(() => text[lang.value] || text.en);
  function setLang(value) {
    if (!text[value]) return;
    lang.value = value;
    localStorage.setItem("language", value);
    document.documentElement.lang = htmlLang[value];
  }
  setLang(lang.value);
  return { lang, t, setLang };
}
