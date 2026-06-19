const DEFAULT_LANGUAGE = "en";

const htmlLang = {
  zh: "zh-CN",
  en: "en",
  ja: "ja"
};

const text = {
  zh: {
    "brand.title": "UMST",
    "language.label": "语言",
    "language.zh": "中文",
    "language.en": "English",
    "language.ja": "日本語",

    "nav.home": "首页",
    "nav.news": "新闻",
    "nav.about": "关于",
    "nav.wiki": "百科",
    "nav.login": "登录",
    "nav.get": "获取",

    "home.title": "探索、战斗、学习",
    "home.explore.title": "探索",
    "home.explore.text": "探索充满无限可能的世界，在变强的同时前往世界的深处与边界。",
    "home.learn.title": "学习",
    "home.learn.text": "通过革命性的节点式学习系统推进你的知识与学习，同时在游戏中不断前进。",

    "news.title": "UMST 新闻",
    "about.title": "关于 UMST",
    "wiki.title": "UMST 百科",
    "get.title": "获取 UMST",

    "login.title": "登录 UMST",
    "login.kicker": "进入知识图谱",
    "login.heading": "解锁你的知识。",
    "login.cardHeading": "欢迎回来",
    "login.username": "用户名",
    "login.password": "密码",
    "login.submit": "登录",
    "login.signup": "创建新账户",
    "login.badLogin": "用户名或密码不正确。",
    "login.note": "连接你的学习路径，继续探索定理、定义、世界与发现。",

    "signup.title": "注册 UMST",
    "signup.kicker": "开始新的知识旅程",
    "signup.heading": "建立你的知识宇宙。",
    "signup.cardHeading": "创建账户",
    "signup.username": "用户名",
    "signup.email": "邮箱",
    "signup.password": "密码",
    "signup.submit": "注册",
    "signup.login": "已有账户？登录",
    "signup.note": "创建账户，保存进度，扩展你的知识图谱。",

    "about.company.title": "关于 UMST",
    "about.company.text": "",

    "team.title": "领导团队",
    "team.field.bio": "简介",
    "team.field.focus": "职责重点",

    "team.chris.name": "Chris",
    "team.chris.role": "创始人 / CTO",
    "team.chris.bio": "剑桥大学学生，热爱数学、技术与音乐。",
    "team.chris.focus": "产品愿景、设计与部署。",

    "team.penny.name": "Penny",
    "team.penny.role": "CFO / CHRO",
    "team.penny.bio": "曾任国营企业计划经营科长12年、上海大型纺织进出口公司业务员4年、上海独资企业副总及贸易部长4年。退休后多年担任民营企业财务主管。",
    "team.penny.focus": "财务管理、人力资源与组织运营。",

    "team.randall.name": "Randall",
    "team.randall.role": "CEO",
    "team.randall.bio": "擅长制定并执行全球战略，尤其关注中国及亚太市场增长，善于结合创新、本地能力与高绩效团队推动业务发展。作为东西方文化之间的桥梁，拥有工业设备、可再生能源、汽车等多个行业及职能领域经验。能够快速评估业务状况并识别机会，擅长应对高难度挑战并带领组织完成转型。兼具商业判断力与技术敏捷性，能够制定可在各层级落地的行动方案。致力于建设包容性团队文化、培养下一代领导者，并凝聚团队实现共同目标。",
    "team.randall.focus": "技术与战略分析、顾问支持与沟通。",

    "team.tina.name": "Tina",
    "team.tina.role": "首席沟通官",
    "team.tina.bio": "纽约大学学生，纽约大学坦登工程学院中国学生学者联合会外联负责人，热爱音乐。",
    "team.tina.focus": "负责沟通策略、社交媒体活动与内容流程管理。",

    "team.kiki.name": "Kiki",
    "team.kiki.role": "首席合规官",
    "team.kiki.bio": "毕业于上海戏剧学院戏剧文学系，并获英国伦敦城市大学大众传播硕士学位。曾任凤凰卫视欧洲台出镜记者、晚间新闻主播、全球24小时新闻连线记者及欧洲华人栏目导演，参与“911事件”“海湾战争”等重大事件报道。曾任上海国际影视节中心新闻部副总监、论坛部副总监、市场部副总监，参与“厉害了我的国”“改革开放40周年”等重大活动策划与执行。后创立上海一达文化传媒有限公司并担任总经理。",
    "team.kiki.focus": "法律与合规顾问。",

    "alt.logo": "UMST 标志",
    "alt.cave": "洞穴",
    "alt.graph": "图谱"
  },

  en: {
    "brand.title": "UMST",
    "dashboard.title": "Dashboard",
    "language.label": "Language",
    "language.zh": "中文",
    "language.en": "English",
    "language.ja": "日本語",

    "nav.home": "Home",
    "nav.news": "News",
    "nav.about": "About",
    "nav.wiki": "Wiki",
    "nav.login": "Login",
    "nav.get": "Get",

    "home.title": "Explore, Fight, Learn",
    "home.explore.title": "Explore",
    "home.explore.text": "Explore a space of endless possibility as you get stronger and venture to the depths and boundaries of the world.",
    "home.learn.title": "Learn",
    "home.learn.text": "Progress your knowledge and your studies with a revolutionary node-based learning system while you progress further in game.",

    "news.title": "UMST News",
    "about.title": "About UMST",
    "wiki.title": "UMST Wiki",
    "get.title": "Get UMST",

    "login.title": "Log in to UMST",
    "login.kicker": "Enter the knowledge graph",
    "login.heading": "Unlock your knowledge.",
    "login.cardHeading": "Welcome back",
    "login.username": "Username",
    "login.password": "Password",
    "login.submit": "Log In",
    "login.signup": "Create a new account",
    "login.badLogin": "Incorrect username or password.",
    "login.note": "Reconnect with your learning path and keep exploring theorems, definitions, worlds, and discoveries.",

    "signup.title": "Sign up for UMST",
    "signup.kicker": "Start your knowledge journey",
    "signup.heading": "Build your knowledge universe.",
    "signup.cardHeading": "Create your account",
    "signup.username": "Username",
    "signup.email": "Email",
    "signup.password": "Password",
    "signup.submit": "Sign Up",
    "signup.login": "Already have an account? Log in",
    "signup.note": "Create an account to save progress and grow your personal knowledge graph.",

    "about.company.title": "About UMST",
    "about.company.text": "",

    "team.title": "Leadership Team",
    "team.field.bio": "Bio",
    "team.field.focus": "Focus",

    "team.chris.name": "Chris",
    "team.chris.role": "Founder / CTO",
    "team.chris.bio": "Student at the University of Cambridge, with strong interests in mathematics, technology, and music.",
    "team.chris.focus": "Product vision, design, and deployment.",

    "team.penny.name": "Penny",
    "team.penny.role": "CFO / CHRO",
    "team.penny.bio": "Previously served for 12 years as Head of Planning and Operations at a state-owned enterprise, 4 years as a business representative at a major Shanghai textile import-export company, and 4 years as Deputy General Manager and Head of Trade at a Shanghai wholly owned enterprise. After retirement, she has spent many years as a finance director for private enterprises.",
    "team.penny.focus": "Financial management, human resources, and organizational operations.",

    "team.randall.name": "Randall",
    "team.randall.role": "CEO",
    "team.randall.bio": "Experienced in developing and deploying global strategies, with a strong focus on China and APAC growth. He specializes in leveraging innovation, local capabilities, and high-performance teams. Serving as a cultural bridge between East and West, his background spans industrial equipment, renewable energy, automotive, and multiple business functions. He quickly assesses businesses, identifies opportunities, and is known for taking on difficult challenges while guiding organizations through change. He combines business acumen with technical agility to create practical plans across all levels of an organization. He is committed to inclusive work cultures, developing future leaders, and aligning teams around a shared vision of success.",
    "team.randall.focus": "Technical and strategic analysis, advisory support, and communication.",

    "team.tina.name": "Tina",
    "team.tina.role": "Chief Communications Officer",
    "team.tina.bio": "Student at NYU, External Affairs Coordinator for NYU Tandon CSSA, and music enthusiast.",
    "team.tina.focus": "Overseeing communication strategy, social media activity, and content pipelines.",

    "team.kiki.name": "Kiki",
    "team.kiki.role": "Chief Compliance Officer",
    "team.kiki.bio": "Graduated from the Department of Dramatic Literature at the Shanghai Theatre Academy and earned a master's degree in Mass Communication from City, University of London. She previously worked as an on-camera reporter, evening news anchor, global 24-hour news correspondent, and director of a European Chinese-language program for Phoenix TV Europe, covering major events including 9/11 and the Gulf War. She later served as Deputy Director of the News Department, Forum Department, and Marketing Department at the Shanghai International Film & TV Festival Center, participating in the planning and execution of major projects and events. She founded Shanghai Yida Culture Media Co., Ltd. and served as General Manager.",
    "team.kiki.focus": "Legal and compliance advisory.",

    "alt.logo": "UMST logo",
    "alt.cave": "The Cave",
    "alt.graph": "The Graph"
  },

  ja: {
    "brand.title": "UMST",
    "language.label": "言語",
    "language.zh": "中文",
    "language.en": "English",
    "language.ja": "日本語",

    "nav.home": "ホーム",
    "nav.news": "ニュース",
    "nav.about": "概要",
    "nav.wiki": "ウィキ",
    "nav.login": "ログイン",
    "nav.get": "入手",

    "home.title": "探索、戦闘、学習",
    "home.explore.title": "探索",
    "home.explore.text": "無限の可能性に満ちた世界を探索し、強くなりながら世界の深部と境界へ進んでいきます。",
    "home.learn.title": "学習",
    "home.learn.text": "革新的なノード型学習システムで知識と学習を進めながら、ゲーム内でもさらに前進します。",

    "news.title": "UMST ニュース",
    "about.title": "UMST について",
    "wiki.title": "UMST ウィキ",
    "get.title": "UMST を入手",

    "login.title": "UMST にログイン",
    "login.kicker": "知識グラフへ",
    "login.heading": "知識を解き放つ。",
    "login.cardHeading": "おかえりなさい",
    "login.username": "ユーザー名",
    "login.password": "パスワード",
    "login.submit": "ログイン",
    "login.signup": "新しいアカウントを作成",
    "login.badLogin": "ユーザー名またはパスワードが正しくありません。",
    "login.note": "学習の道筋に戻り、定理、定義、世界、発見をさらに探索しましょう。",

    "signup.title": "UMST に登録",
    "signup.kicker": "新しい知識の旅へ",
    "signup.heading": "知識の宇宙を築く。",
    "signup.cardHeading": "アカウント作成",
    "signup.username": "ユーザー名",
    "signup.email": "メール",
    "signup.password": "パスワード",
    "signup.submit": "登録",
    "signup.login": "すでにアカウントがありますか？ログイン",
    "signup.note": "アカウントを作成して進行状況を保存し、自分だけの知識グラフを広げましょう。",

    "about.company.title": "UMST について",
    "about.company.text": "",

    "team.title": "リーダーシップチーム",
    "team.field.bio": "プロフィール",
    "team.field.focus": "担当領域",

    "team.chris.name": "Chris",
    "team.chris.role": "創設者 / CTO",
    "team.chris.bio": "ケンブリッジ大学の学生。数学、テクノロジー、音楽に強い関心を持つ。",
    "team.chris.focus": "プロダクトビジョン、設計、デプロイメント。",

    "team.penny.name": "Penny",
    "team.penny.role": "CFO / CHRO",
    "team.penny.bio": "国有企業で計画経営部門の責任者を12年間、上海の大手繊維輸出入会社で営業担当を4年間、上海の外資独資企業で副総経理および貿易部長を4年間務めた。退職後は長年にわたり民間企業の財務責任者として活動している。",
    "team.penny.focus": "財務管理、人事、組織運営。",

    "team.randall.name": "Randall",
    "team.randall.role": "CEO",
    "team.randall.bio": "中国およびAPAC地域での成長を重視したグローバル戦略の策定と実行に豊富な経験を持つ。イノベーション、現地の能力、高い成果を出すチームを活用して事業成長を推進する。東西文化の橋渡し役として、産業機器、再生可能エネルギー、自動車など複数の業界と職能領域にわたる経験を有する。事業を素早く評価し、機会を見出し、困難な課題に取り組みながら組織変革を導くことで知られている。優れたビジネス判断力と技術的な柔軟性を兼ね備え、組織の各階層で実行可能な計画を作成できる。包摂的な職場文化の構築、次世代リーダーの育成、共通の成功ビジョンに向けたチームの結集に尽力している。",
    "team.randall.focus": "技術・戦略分析、アドバイザリー、コミュニケーション。",

    "team.tina.name": "Tina",
    "team.tina.role": "最高コミュニケーション責任者",
    "team.tina.bio": "ニューヨーク大学の学生。NYU Tandon CSSAの渉外担当コーディネーターであり、音楽を愛好している。",
    "team.tina.focus": "コミュニケーション戦略、ソーシャルメディア活動、コンテンツ運用フローの統括。",

    "team.kiki.name": "Kiki",
    "team.kiki.role": "最高コンプライアンス責任者",
    "team.kiki.bio": "上海戯劇学院戯劇文学科を卒業し、英国ロンドン大学シティ校でマスコミュニケーションの修士号を取得。Phoenix TV Europeで現場記者、夜間ニュースキャスター、24時間グローバルニュース中継記者、欧州華人向け番組のディレクターを務め、「9.11事件」や「湾岸戦争」などの重大事件報道に携わった。その後、上海国際映画テレビ祭センターでニュース部、フォーラム部、マーケティング部の副責任者を務め、重要なプロジェクトや大型イベントの企画・実行に参加。上海一達文化伝媒有限公司を創設し、総経理を務めた。",
    "team.kiki.focus": "法務・コンプライアンスアドバイザー。",

    "alt.logo": "UMST ロゴ",
    "alt.cave": "洞窟",
    "alt.graph": "グラフ"
  }
};

function setLanguage(lang) {
  if (!text[lang]) lang = DEFAULT_LANGUAGE;

  localStorage.setItem("language", lang);
  document.documentElement.lang = htmlLang[lang];

  document.querySelectorAll("[data-i18n]").forEach(el => {
    el.textContent = text[lang][el.dataset.i18n] || "";
  });

  document.querySelectorAll("[data-i18n-alt]").forEach(el => {
    el.alt = text[lang][el.dataset.i18nAlt] || "";
  });

  const titleKey = document.body.dataset.title;
  if (titleKey) document.title = text[lang][titleKey] || "";

  document.querySelectorAll("[data-language-dropdown]").forEach(el => {
    el.classList.remove("open");
  });
}

setLanguage(localStorage.getItem("language") || DEFAULT_LANGUAGE);

document.querySelectorAll("[data-language-button]").forEach(button => {
  button.addEventListener("click", () => {
    button.nextElementSibling.classList.toggle("open");
  });
});

document.querySelectorAll("[data-language-choice]").forEach(button => {
  button.addEventListener("click", () => {
    setLanguage(button.dataset.languageChoice);
  });
});

document.addEventListener("click", event => {
  if (event.target.closest(".language-menu")) return;

  document.querySelectorAll("[data-language-dropdown]").forEach(el => {
    el.classList.remove("open");
  });
});