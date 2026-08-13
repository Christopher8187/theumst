import { computed, ref } from "vue";

const htmlLang = { en: "en", zh: "zh-CN", ja: "ja" };

const en = {
  language: "Language", chooseLanguage: "Choose your language", chooseLanguageText: "Select the language to use in the dashboard.",
  home: "Home", profile: "Profile", apiKeys: "API Keys", books: "Books", media: "Media", admin: "Admin", superadmin: "Superadmin", signOut: "Sign out",
  dateLocale: "en-GB", roleUser: "User", roleManager: "Manager", roleAdmin: "Admin", roleSuperadmin: "Superadmin", fileTypeFile: "File", fileTypeFolder: "Folder",
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
  teamAccess: "Team access", managerAccessTitle: "Manager authority", managerAccessText: "Managers can maintain the book catalog and newsroom. They do not receive database, Qdrant, object-storage, or superadmin access.", usernameOrEmail: "Username or email", makeManager: "Make manager", managerGranted: "is now a manager.",
  libraryOperations: "Library operations", booksTitle: "Books", booksText: "Maintain the source catalog that feeds the structured knowledge and AI training ecosystem.", booksTracked: "books tracked", sectionsMapped: "sections mapped", knowledgeObjects: "knowledge objects", newEntry: "New entry", editing: "Editing", addBook: "Add book", editBook: "Edit book", cancel: "Cancel", bookTitle: "Title", bookTitlePlaceholder: "e.g. Linear Algebra Done Right", publisher: "Publisher", isbn: "ISBN", publishDate: "Publish date", version: "Version", sourceKey: "Source key", saveChanges: "Save changes", catalog: "Catalog", currentBooks: "Current books", unknownPublisher: "Publisher not set", dateNotSet: "Date not set", sections: "sections", objects: "objects", edit: "Edit", noBooks: "No books yet", noBooksText: "Add the first source book using the form.", bookSaved: "Book saved.", bookDeleted: "Book and its connected content deleted.", deleteBookConfirm: "Permanently delete",
  editorialDesk: "Editorial desk", mediaTitle: "Media", mediaText: "Publish updates here and they appear automatically on the public website.", newStory: "New story", editPost: "Edit post", publishUpdate: "Publish an update", headline: "Headline", headlinePlaceholder: "What should the community know?", excerpt: "Summary", excerptPlaceholder: "A concise introduction for the news card.", story: "Story", storyPlaceholder: "Write the full update…", imageUrl: "Image URL", status: "Status", published: "Published", draft: "Draft", publishNow: "Publish now", saveDraft: "Save draft", newsroom: "Newsroom", allPosts: "All posts", noPosts: "No posts yet", noPostsText: "Create the first public update using the form.", postSaved: "Post saved. Published posts are now live.", postDeleted: "Post deleted.", deletePostConfirm: "Delete",
  superadminTitle: "Superadmin", superadminText: "Promote users to admin and perform unrestricted database administration.", userToPromote: "User", giveAdmin: "Give admin", adminGranted: "is now an admin.",
  superSql: "Database administration", superSqlTitle: "Arbitrary PostgreSQL", superSqlText: "This executes exactly the PostgreSQL supplied below. It is intentionally available only to superadmins.", sqlCode: "SQL code", runSql: "Run SQL"
};

const zh = {
  ...en,
  language: "语言", chooseLanguage: "选择语言", chooseLanguageText: "选择控制台使用的语言。",
  home: "首页", profile: "个人资料", apiKeys: "API 密钥", books: "书籍", media: "媒体", admin: "管理员", superadmin: "超级管理员", signOut: "退出登录",
  dateLocale: "zh-CN", roleUser: "用户", roleManager: "经理", roleAdmin: "管理员", roleSuperadmin: "超级管理员", fileTypeFile: "文件", fileTypeFolder: "文件夹",
  identity: "知识身份", profileTitle: "个人资料", profileText: "更新与你的 UMST 账户关联的公开信息。", username: "用户名", email: "邮箱", alias: "昵称", description: "简介", saveProfile: "保存资料", saved: "资料已保存。", authorityType: "权限类型",
  developer: "开发者访问", apiTitle: "API 密钥", apiText: "普通密钥提供限速读取。管理员和超级管理员可以将自己的密钥升级为不限速的主密钥，用于提交知识、嵌入和写入存储。",
  keyName: "密钥名称", keyNameRequired: "请输入密钥名称。", createKey: "创建 API 密钥", newKey: "新密钥：", active: "启用", revoked: "已撤销", revoke: "撤销", regularKey: "普通密钥", masterKey: "主密钥", requestsPerHour: "次请求/小时", unlimitedMaster: "不限速读取、知识提交、嵌入和存储写入。", upgradeMaster: "升级为主密钥", upgradeMasterConfirm: "将此密钥升级为不限速主密钥？控制台中无法撤销。", masterUpgraded: "API 密钥已升级为主密钥。",
  adminTitle: "管理员工具", adminText: "在 Qdrant 中搜索语义投影并管理对象存储。任意 SQL 仅限超级管理员页面。", vectorSearch: "语义搜索", qdrantTitle: "Qdrant 搜索", qdrantText: "配置嵌入提供商后可用文本搜索，也可以直接粘贴向量。", queryText: "查询文本", queryTextPlaceholder: "这是什么的例子？", queryVector: "查询向量（可选）", filtersJson: "JSON 载荷过滤器", resultLimit: "结果数量", searchQdrant: "搜索 Qdrant", invalidJson: "JSON 无效",
  files: "文件", objectStorage: "对象存储", storageText: "当前连接到 SERVER=", refresh: "刷新", up: "上一级", newFolder: "新文件夹名称", createFolder: "创建文件夹", newFile: "新建文本文件", upload: "上传文件", download: "下载", delete: "删除", emptyFolder: "这个文件夹是空的。", filePath: "文件路径", fileContent: "文本内容", saveFile: "保存文件", storageLoaded: "存储已加载。", storageFileLoaded: "文件已加载。", storagePathRequired: "请输入文件路径。", storageSaved: "文件已保存。", folderNameRequired: "请输入文件夹名称。", folderCreated: "文件夹已创建。", fileUploaded: "文件已上传。", deleteConfirm: "删除", deleted: "已删除。", newFileReady: "请输入路径和内容，然后保存。",
  teamAccess: "团队权限", managerAccessTitle: "经理权限", managerAccessText: "经理可以维护书籍目录和新闻中心，但不能访问数据库、Qdrant、对象存储或超级管理员功能。", usernameOrEmail: "用户名或邮箱", makeManager: "设为经理", managerGranted: "已成为经理。",
  libraryOperations: "书库运营", booksTitle: "书籍", booksText: "维护为结构化知识和 AI 训练生态系统提供来源的书籍目录。", booksTracked: "本书", sectionsMapped: "个章节已映射", knowledgeObjects: "个知识对象", newEntry: "新条目", editing: "正在编辑", addBook: "添加书籍", editBook: "编辑书籍", cancel: "取消", bookTitle: "书名", bookTitlePlaceholder: "例如：《线性代数应该这样学》", publisher: "出版社", isbn: "ISBN", publishDate: "出版日期", version: "版本", sourceKey: "来源标识", saveChanges: "保存更改", catalog: "目录", currentBooks: "当前书籍", unknownPublisher: "未设置出版社", dateNotSet: "未设置日期", sections: "个章节", objects: "个对象", edit: "编辑", noBooks: "暂无书籍", noBooksText: "使用表单添加第一本来源书籍。", bookSaved: "书籍已保存。", bookDeleted: "书籍及其关联内容已删除。", deleteBookConfirm: "永久删除",
  editorialDesk: "编辑工作台", mediaTitle: "媒体", mediaText: "在这里发布动态，内容会自动显示在公开网站上。", newStory: "新文章", editPost: "编辑文章", publishUpdate: "发布动态", headline: "标题", headlinePlaceholder: "希望社区了解什么？", excerpt: "摘要", excerptPlaceholder: "为新闻卡片撰写简洁的导语。", story: "正文", storyPlaceholder: "撰写完整动态…", imageUrl: "图片网址", status: "状态", published: "已发布", draft: "草稿", publishNow: "立即发布", saveDraft: "保存草稿", newsroom: "新闻中心", allPosts: "全部文章", noPosts: "暂无文章", noPostsText: "使用表单创建第一篇公开动态。", postSaved: "文章已保存，已发布的内容现已上线。", postDeleted: "文章已删除。", deletePostConfirm: "删除",
  superadminTitle: "超级管理员", superadminText: "将用户提升为管理员并执行不受限制的数据库管理。", userToPromote: "用户", giveAdmin: "授予管理员", adminGranted: "现在是管理员。", superSql: "数据库管理", superSqlTitle: "任意 PostgreSQL", superSqlText: "这里会执行你提供的 PostgreSQL，因此仅向超级管理员开放。", sqlCode: "SQL 代码", runSql: "运行 SQL"
};

const ja = {
  ...en,
  language: "言語", chooseLanguage: "言語を選択", chooseLanguageText: "ダッシュボードで使用する言語を選択します。",
  home: "ホーム", profile: "プロフィール", apiKeys: "APIキー", books: "書籍", media: "メディア", admin: "管理者", superadmin: "スーパー管理者", signOut: "ログアウト",
  dateLocale: "ja-JP", roleUser: "ユーザー", roleManager: "マネージャー", roleAdmin: "管理者", roleSuperadmin: "スーパー管理者", fileTypeFile: "ファイル", fileTypeFolder: "フォルダー",
  identity: "知識アイデンティティ", profileTitle: "プロフィール", profileText: "UMST アカウントに紐づく公開情報を更新します。", username: "ユーザー名", email: "メール", alias: "別名", description: "説明", saveProfile: "保存", saved: "プロフィールを保存しました。", authorityType: "権限タイプ",
  developer: "開発者アクセス", apiTitle: "APIキー", apiText: "通常キーは制限付き読み取りアクセスを提供します。管理者とスーパー管理者は自分のキーを無制限のマスターキーへ昇格できます。",
  keyName: "キー名", keyNameRequired: "キー名を入力してください。", createKey: "APIキーを作成", newKey: "新しいキー：", active: "有効", revoked: "無効", revoke: "無効化", regularKey: "通常キー", masterKey: "マスターキー", requestsPerHour: "リクエスト/時", unlimitedMaster: "無制限の読み取り、知識送信、埋め込み、ストレージ書き込み。", upgradeMaster: "マスターへ昇格", upgradeMasterConfirm: "このキーを無制限のマスターキーへ昇格しますか？ダッシュボードから元に戻せません。", masterUpgraded: "APIキーをマスターへ昇格しました。",
  adminTitle: "管理者ツール", adminText: "Qdrant の意味投影を検索し、オブジェクトストレージを管理します。任意SQLはスーパー管理者ページ限定です。", vectorSearch: "意味検索", qdrantTitle: "Qdrant 検索", qdrantText: "埋め込みプロバイダー設定時はテキスト検索、またはベクトルを直接貼り付けできます。", queryText: "検索テキスト", queryTextPlaceholder: "これは何の例ですか？", queryVector: "検索ベクトル（任意）", filtersJson: "JSONペイロードフィルター", resultLimit: "結果数", searchQdrant: "Qdrantを検索", invalidJson: "JSONが無効です",
  files: "ファイル", objectStorage: "オブジェクトストレージ", storageText: "接続先 SERVER=", refresh: "更新", up: "上へ", newFolder: "新しいフォルダ名", createFolder: "フォルダ作成", newFile: "新しいテキスト", upload: "アップロード", download: "ダウンロード", delete: "削除", emptyFolder: "このフォルダは空です。", filePath: "ファイルパス", fileContent: "テキスト内容", saveFile: "保存", storageLoaded: "ストレージを読み込みました。", storageFileLoaded: "ファイルを読み込みました。", storagePathRequired: "ファイルパスを入力してください。", storageSaved: "保存しました。", folderNameRequired: "フォルダ名を入力してください。", folderCreated: "フォルダを作成しました。", fileUploaded: "アップロードしました。", deleteConfirm: "削除", deleted: "削除しました。", newFileReady: "パスと内容を入力して保存してください。",
  teamAccess: "チームアクセス", managerAccessTitle: "マネージャー権限", managerAccessText: "マネージャーは書籍カタログとニュースルームを管理できます。データベース、Qdrant、オブジェクトストレージ、スーパー管理者機能にはアクセスできません。", usernameOrEmail: "ユーザー名またはメール", makeManager: "マネージャーにする", managerGranted: "さんをマネージャーに設定しました。",
  libraryOperations: "ライブラリ運営", booksTitle: "書籍", booksText: "構造化知識と AI 訓練エコシステムの情報源となる書籍カタログを管理します。", booksTracked: "冊を管理中", sectionsMapped: "セクションをマッピング済み", knowledgeObjects: "個の知識オブジェクト", newEntry: "新規登録", editing: "編集中", addBook: "書籍を追加", editBook: "書籍を編集", cancel: "キャンセル", bookTitle: "書名", bookTitlePlaceholder: "例：Linear Algebra Done Right", publisher: "出版社", isbn: "ISBN", publishDate: "出版日", version: "版", sourceKey: "ソースキー", saveChanges: "変更を保存", catalog: "カタログ", currentBooks: "登録済み書籍", unknownPublisher: "出版社未設定", dateNotSet: "日付未設定", sections: "セクション", objects: "オブジェクト", edit: "編集", noBooks: "書籍はまだありません", noBooksText: "フォームから最初の資料書籍を追加してください。", bookSaved: "書籍を保存しました。", bookDeleted: "書籍と関連コンテンツを削除しました。", deleteBookConfirm: "完全に削除",
  editorialDesk: "編集デスク", mediaTitle: "メディア", mediaText: "ここで更新を公開すると、公開サイトに自動的に表示されます。", newStory: "新しい記事", editPost: "記事を編集", publishUpdate: "更新を公開", headline: "見出し", headlinePlaceholder: "コミュニティに何を伝えますか？", excerpt: "要約", excerptPlaceholder: "ニュースカード用の簡潔な紹介文。", story: "本文", storyPlaceholder: "更新の全文を入力…", imageUrl: "画像 URL", status: "ステータス", published: "公開済み", draft: "下書き", publishNow: "今すぐ公開", saveDraft: "下書きを保存", newsroom: "ニュースルーム", allPosts: "すべての記事", noPosts: "記事はまだありません", noPostsText: "フォームから最初の公開記事を作成してください。", postSaved: "記事を保存しました。公開済みの記事はサイトに反映されています。", postDeleted: "記事を削除しました。", deletePostConfirm: "削除",
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
