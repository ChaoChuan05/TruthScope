"use strict";

window.TRUTHSCOPE_TERMS = Object.freeze({
  version: "2026-09-05-2",
  documents: Object.freeze({
    en: {
      title: "Terms and Conditions",
      effectiveDate: "Effective 5 September 2026",
      introduction:
        "These terms govern use of TruthScope, an experimental evidence-first claim verification service maintained by the TruthScope project team. By accepting, you confirm that you have read and agree to these terms.",
      sections: [
        {
          title: "1. Service purpose",
          paragraphs: [
            "TruthScope analyses user-submitted text or public URLs, retrieves public evidence, compares AI model assessments, and presents evidence-support scores, summaries, disagreements, and technical metadata.",
            "The service is a hackathon prototype provided for information and research. It is not an official fact-checking authority and does not provide legal, medical, financial, electoral, or other professional advice.",
          ],
        },
        {
          title: "2. AI and evidence limitations",
          paragraphs: [
            "AI output may be inaccurate, incomplete, biased, outdated, or unavailable. Sources may also be incomplete or wrong. An Evidence Support score describes support within evidence collected for that run; it is not a probability that a claim is true.",
            "Review original sources, dates, limitations, model disagreements, and request metadata before relying on a result. Do not use TruthScope as the sole basis for a critical decision.",
          ],
        },
        {
          title: "3. Accounts and access",
          paragraphs: [
            "Google and GitHub sign-in are handled through Supabase Auth. You are responsible for access to your selected provider account and for activity performed through your TruthScope session. Do not attempt to access another user's account or history.",
            "You may decline these terms and sign out. Full verification and private-history features remain unavailable until you accept the current terms version.",
          ],
        },
        {
          title: "4. Acceptable use",
          paragraphs: [
            "Use TruthScope only for lawful purposes. Do not submit unlawful, defamatory, harassing, private, confidential, or rights-infringing material; automate abusive traffic; manipulate verification; probe for secrets; bypass access controls; disrupt the service; or falsely present a result as guaranteed truth or an official ruling.",
            "Treat people and organisations mentioned in claims responsibly. You remain responsible for submitted content and for how you use or share results.",
          ],
        },
        {
          title: "5. Data and external services",
          paragraphs: [
            "TruthScope uses basic profile and email information from your selected Google or GitHub account for authentication and ownership of private history. Submitted claims, public URLs, verification outputs, source metadata, and provider request IDs may be processed or stored to provide the service.",
            "Supabase provides authentication and persistence. Gonka Router and routed model providers process AI inference requests. Brave Search receives search queries used to find public evidence. Public source websites receive ordinary retrieval requests. Their own terms and privacy practices also apply.",
            "Do not submit secrets or sensitive personal data. Browser preferences and this acceptance record are stored locally on this browser. A local acceptance record does not synchronise across browsers or devices.",
          ],
        },
        {
          title: "6. Sources and intellectual property",
          paragraphs: [
            "Third-party articles, pages, names, trademarks, and other source materials belong to their respective owners. Links are provided for review and do not imply endorsement.",
            "TruthScope interface and project code remain subject to their applicable repository licence. You keep any rights you already hold in content you submit; you permit its processing only as needed to operate and secure the requested verification workflow.",
          ],
        },
        {
          title: "7. Availability, changes, and suspension",
          paragraphs: [
            "The prototype may be slow, degraded, interrupted, changed, or discontinued without notice. External model, search, authentication, storage, source, and tunnel services may fail independently.",
            "Access may be restricted or suspended when reasonably necessary to protect users, the service, or third parties, or to respond to suspected misuse or legal obligations.",
          ],
        },
        {
          title: "8. Disclaimer and liability",
          paragraphs: [
            "To the extent permitted by law, TruthScope is provided “as is” and “as available”, without warranties of accuracy, completeness, fitness, availability, non-infringement, or reliability.",
            "To the extent permitted by law, the project team is not liable for indirect, incidental, special, consequential, or punitive loss arising from use of, inability to use, or reliance on the service. Rights that cannot lawfully be excluded remain unaffected.",
          ],
        },
        {
          title: "9. Governing law",
          paragraphs: [
            "These terms are governed by the laws of Malaysia, without limiting any mandatory rights or protections that apply to you.",
          ],
        },
        {
          title: "10. Term updates and contact",
          paragraphs: [
            "A changed terms version may require fresh acceptance before continued use. The effective date above identifies this version.",
            "For questions, data requests, or concerns, contact the deployment owner or project maintainer through the TruthScope project repository.",
          ],
        },
      ],
      scrollPrompt: "Scroll through all terms to continue.",
      readComplete: "End reached. Confirm acceptance below.",
      acceptance: "I have read and agree to the Terms and Conditions.",
      acceptButton: "Accept and continue",
      declineButton: "Decline and sign out",
      languageLabel: "Terms language",
      repositoryLabel: "TruthScope project repository",
    },
    ms: {
      title: "Terma dan Syarat",
      effectiveDate: "Berkuat kuasa 5 September 2026",
      introduction:
        "Terma ini mengawal penggunaan TruthScope, perkhidmatan percubaan untuk mengesahkan dakwaan berasaskan bukti yang diselenggara oleh pasukan projek TruthScope. Dengan menerima, anda mengesahkan bahawa anda telah membaca dan bersetuju dengan terma ini.",
      sections: [
        {
          title: "1. Tujuan perkhidmatan",
          paragraphs: [
            "TruthScope menganalisis teks atau URL awam yang dihantar pengguna, mendapatkan bukti awam, membandingkan penilaian model AI, serta memaparkan skor sokongan bukti, ringkasan, percanggahan dan metadata teknikal.",
            "Perkhidmatan ini ialah prototaip hackathon untuk tujuan maklumat dan penyelidikan. Ia bukan pihak berkuasa semakan fakta rasmi dan tidak memberikan nasihat undang-undang, perubatan, kewangan, pilihan raya atau profesional lain.",
          ],
        },
        {
          title: "2. Batasan AI dan bukti",
          paragraphs: [
            "Output AI mungkin tidak tepat, tidak lengkap, berat sebelah, lapuk atau tidak tersedia. Sumber juga mungkin tidak lengkap atau salah. Skor Sokongan Bukti menerangkan sokongan dalam bukti yang dikumpulkan untuk semakan tersebut; ia bukan kebarangkalian bahawa sesuatu dakwaan itu benar.",
            "Semak sumber asal, tarikh, batasan, percanggahan model dan metadata permintaan sebelum bergantung pada hasil. Jangan gunakan TruthScope sebagai satu-satunya asas bagi keputusan kritikal.",
          ],
        },
        {
          title: "3. Akaun dan akses",
          paragraphs: [
            "Log masuk Google dan GitHub dikendalikan melalui Supabase Auth. Anda bertanggungjawab terhadap akses kepada akaun penyedia pilihan anda dan aktiviti melalui sesi TruthScope anda. Jangan cuba mengakses akaun atau sejarah pengguna lain.",
            "Anda boleh menolak terma ini dan log keluar. Ciri pengesahan penuh dan sejarah peribadi tidak tersedia sehingga anda menerima versi terma semasa.",
          ],
        },
        {
          title: "4. Penggunaan yang dibenarkan",
          paragraphs: [
            "Gunakan TruthScope hanya untuk tujuan yang sah. Jangan hantar bahan yang menyalahi undang-undang, memfitnah, mengganggu, bersifat peribadi, sulit atau melanggar hak; mengautomasi trafik yang menyalahguna; memanipulasi pengesahan; mencari rahsia; memintas kawalan akses; mengganggu perkhidmatan; atau menggambarkan hasil sebagai kebenaran terjamin atau keputusan rasmi.",
            "Layan individu dan organisasi yang disebut dalam dakwaan secara bertanggungjawab. Anda bertanggungjawab terhadap kandungan yang dihantar serta cara hasil digunakan atau dikongsi.",
          ],
        },
        {
          title: "5. Data dan perkhidmatan luar",
          paragraphs: [
            "TruthScope menggunakan profil asas dan e-mel daripada akaun Google atau GitHub pilihan anda untuk pengesahan serta pemilikan sejarah peribadi. Dakwaan, URL awam, output pengesahan, metadata sumber dan ID permintaan penyedia mungkin diproses atau disimpan untuk menyediakan perkhidmatan.",
            "Supabase menyediakan pengesahan dan penyimpanan. Gonka Router serta penyedia model yang diarahkan memproses permintaan inferens AI. Brave Search menerima pertanyaan carian untuk mencari bukti awam. Laman sumber awam menerima permintaan capaian biasa. Terma dan amalan privasi mereka turut terpakai.",
            "Jangan hantar rahsia atau data peribadi sensitif. Keutamaan pelayar dan rekod penerimaan ini disimpan secara setempat dalam pelayar ini. Rekod penerimaan setempat tidak diselaraskan antara pelayar atau peranti.",
          ],
        },
        {
          title: "6. Sumber dan harta intelek",
          paragraphs: [
            "Artikel, halaman, nama, tanda dagangan dan bahan sumber pihak ketiga ialah milik pemilik masing-masing. Pautan diberikan untuk semakan dan tidak bermaksud pengendorsan.",
            "Antara muka dan kod projek TruthScope tertakluk kepada lesen repositori yang berkenaan. Anda mengekalkan hak yang sedia ada terhadap kandungan yang dihantar; anda membenarkan pemprosesannya hanya setakat yang diperlukan untuk mengendalikan dan melindungi aliran pengesahan yang diminta.",
          ],
        },
        {
          title: "7. Ketersediaan, perubahan dan penggantungan",
          paragraphs: [
            "Prototaip mungkin perlahan, terhad, terganggu, diubah atau dihentikan tanpa notis. Perkhidmatan model, carian, pengesahan, penyimpanan, sumber dan tunnel luar mungkin gagal secara berasingan.",
            "Akses boleh dihadkan atau digantung apabila munasabah untuk melindungi pengguna, perkhidmatan atau pihak ketiga, atau untuk menangani penyalahgunaan yang disyaki atau kewajipan undang-undang.",
          ],
        },
        {
          title: "8. Penafian dan liabiliti",
          paragraphs: [
            "Setakat yang dibenarkan undang-undang, TruthScope disediakan “seadanya” dan “sebagaimana tersedia”, tanpa jaminan ketepatan, kelengkapan, kesesuaian, ketersediaan, ketiadaan pelanggaran atau kebolehpercayaan.",
            "Setakat yang dibenarkan undang-undang, pasukan projek tidak bertanggungjawab terhadap kerugian tidak langsung, sampingan, khas, berbangkit atau punitif akibat penggunaan, ketidakupayaan menggunakan atau pergantungan pada perkhidmatan. Hak yang tidak boleh dikecualikan di sisi undang-undang kekal tidak terjejas.",
          ],
        },
        {
          title: "9. Undang-undang yang mentadbir",
          paragraphs: [
            "Terma ini ditadbir oleh undang-undang Malaysia tanpa mengehadkan hak atau perlindungan mandatori yang terpakai kepada anda.",
          ],
        },
        {
          title: "10. Kemas kini terma dan hubungan",
          paragraphs: [
            "Versi terma yang berubah mungkin memerlukan penerimaan baharu sebelum penggunaan diteruskan. Tarikh kuat kuasa di atas mengenal pasti versi ini.",
            "Untuk pertanyaan, permintaan data atau kebimbangan, hubungi pemilik deployment atau penyelenggara projek melalui repositori projek TruthScope.",
          ],
        },
      ],
      scrollPrompt: "Tatal dan baca semua terma untuk teruskan.",
      readComplete: "Sudah sampai ke penghujung. Sahkan penerimaan di bawah.",
      acceptance: "Saya telah membaca dan bersetuju dengan Terma dan Syarat.",
      acceptButton: "Terima dan teruskan",
      declineButton: "Tolak dan log keluar",
      languageLabel: "Bahasa terma",
      repositoryLabel: "Repositori projek TruthScope",
    },
    "zh-CN": {
      title: "条款与条件",
      effectiveDate: "生效日期：2026年9月5日",
      introduction:
        "本条款适用于 TruthScope。TruthScope 是由 TruthScope 项目团队维护的实验性、证据优先说法核查服务。选择接受即表示你已阅读并同意本条款。",
      sections: [
        {
          title: "1. 服务目的",
          paragraphs: [
            "TruthScope 分析用户提交的文字或公开 URL，检索公开证据，对比 AI 模型评估，并展示证据支持分数、摘要、分歧和技术元数据。",
            "本服务是用于信息和研究的黑客松原型，并非官方事实核查机构，也不提供法律、医疗、金融、选举或其他专业意见。",
          ],
        },
        {
          title: "2. AI 与证据限制",
          paragraphs: [
            "AI 输出可能不准确、不完整、有偏差、过时或不可用；来源本身也可能不完整或错误。证据支持分数只描述本次核查所收集证据的支持程度，并非说法为真的概率。",
            "依赖结果前，请查阅原始来源、日期、限制、模型分歧和请求元数据。请勿将 TruthScope 作为关键决策的唯一依据。",
          ],
        },
        {
          title: "3. 账户与访问",
          paragraphs: [
            "Google 和 GitHub 登录由 Supabase Auth 处理。你须对所选登录服务商账户的访问权限及 TruthScope 会话中的活动负责。请勿尝试访问其他用户的账户或历史记录。",
            "你可以拒绝本条款并退出登录。在接受当前版本条款前，完整核查和私人历史功能不可使用。",
          ],
        },
        {
          title: "4. 可接受使用",
          paragraphs: [
            "仅可将 TruthScope 用于合法目的。不得提交违法、诽谤、骚扰、私人、机密或侵权材料；不得制造滥用流量、操纵核查、探查机密、绕过访问控制、干扰服务，或将结果虚假描述为保证正确或官方裁决。",
            "请负责任地对待说法中提及的个人和组织。你须对提交内容以及结果的使用或分享方式负责。",
          ],
        },
        {
          title: "5. 数据与外部服务",
          paragraphs: [
            "TruthScope 使用你所选 Google 或 GitHub 账户的基本个人资料和电子邮件进行身份验证，并确定私人历史记录的所有权。为提供服务，系统可能处理或存储提交的说法、公开 URL、核查输出、来源元数据和服务商请求 ID。",
            "Supabase 提供身份验证和持久化存储；Gonka Router 及其路由的模型服务商处理 AI 推理请求；Brave Search 接收用于寻找公开证据的搜索查询；公开来源网站会收到普通访问请求。它们各自的条款和隐私做法亦适用。",
            "请勿提交秘密或敏感个人数据。浏览器偏好和本次接受记录保存在当前浏览器中，不会在不同浏览器或设备之间同步。",
          ],
        },
        {
          title: "6. 来源与知识产权",
          paragraphs: [
            "第三方文章、网页、名称、商标和其他来源材料归各自所有者所有。链接仅供查阅，不代表认可。",
            "TruthScope 界面和项目代码受适用的代码仓库许可证约束。你保留原本对提交内容拥有的权利，并允许系统仅在运行和保护所请求核查流程所需的范围内处理该内容。",
          ],
        },
        {
          title: "7. 可用性、变更与暂停",
          paragraphs: [
            "本原型可能缓慢、降级、中断、变更或在不另行通知的情况下停止。外部模型、搜索、身份验证、存储、来源和 tunnel 服务可能各自发生故障。",
            "为保护用户、服务或第三方，或应对疑似滥用及法律义务，项目团队可在合理必要时限制或暂停访问。",
          ],
        },
        {
          title: "8. 免责声明与责任限制",
          paragraphs: [
            "在法律允许范围内，TruthScope 按“现状”和“可用状态”提供，不保证准确性、完整性、适用性、可用性、不侵权或可靠性。",
            "在法律允许范围内，项目团队不对因使用、无法使用或依赖本服务而产生的间接、附带、特殊、后果性或惩罚性损失负责。法律规定不得排除的权利不受影响。",
          ],
        },
        {
          title: "9. 适用法律",
          paragraphs: [
            "本条款受马来西亚法律管辖，但不限制适用于你的任何强制性权利或保护。",
          ],
        },
        {
          title: "10. 条款更新与联系",
          paragraphs: [
            "条款版本变更后，你可能需要重新接受才能继续使用。上方生效日期用于识别当前版本。",
            "如有疑问、数据请求或疑虑，请通过 TruthScope 项目代码仓库联系部署负责人或项目维护者。",
          ],
        },
      ],
      scrollPrompt: "请滚动并阅读全部条款后继续。",
      readComplete: "已到达末尾，请在下方确认接受。",
      acceptance: "我已阅读并同意条款与条件。",
      acceptButton: "接受并继续",
      declineButton: "拒绝并退出",
      languageLabel: "条款语言",
      repositoryLabel: "TruthScope 项目代码仓库",
    },
  }),
});
