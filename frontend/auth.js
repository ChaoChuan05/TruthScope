(() => {
  // Legacy standalone auth helper. Main application owns auth in script.js.
  const appConfig = window.TRUTHSCOPE_CONFIG || {};
  const SUPABASE_URL = String(appConfig.SUPABASE_URL || "");
  const SUPABASE_PUBLISHABLE_KEY = String(appConfig.SUPABASE_PUBLISHABLE_KEY || "");
  const OAUTH_REDIRECT_URL = String(
    appConfig.OAUTH_REDIRECT_URL || window.location.origin + window.location.pathname
  );

  if (!window.supabase || !SUPABASE_URL || !SUPABASE_PUBLISHABLE_KEY) {
    console.error("Supabase browser configuration failed to load.");
    return;
  }

  const supabaseClient = window.supabase.createClient(
    SUPABASE_URL,
    SUPABASE_PUBLISHABLE_KEY
  );

  /*
   * 提供给其他 JavaScript 文件使用。
   * 之后 script.js 可以通过 window.truthScopeSupabase 访问 Supabase。
   */
  window.truthScopeSupabase = supabaseClient;

  const openLoginBtn = document.getElementById("openLoginBtn");
  const closeLoginBtn = document.getElementById("closeLoginBtn");
  const loginModal = document.getElementById("loginModal");
  const googleLoginBtn = document.getElementById("googleLoginBtn");
  const githubLoginBtn = document.getElementById('githubLoginBtn');
  const logoutBtn = document.getElementById("logoutBtn");
  const userPanel = document.getElementById("userPanel");
  const userAvatar = document.getElementById("userAvatar");
  const userDisplayName = document.getElementById("userDisplayName");
  const authMessage = document.getElementById("authMessage");

  function openLoginModal() {
    authMessage.textContent = "";
    loginModal.hidden = false;
    document.body.classList.add("auth-modal-open");
    googleLoginBtn.focus();
  }

  function closeLoginModal() {
    loginModal.hidden = true;
    document.body.classList.remove("auth-modal-open");
  }

  function showLoggedOutUI() {
    openLoginBtn.hidden = false;
    userPanel.hidden = true;
    userAvatar.removeAttribute("src");
    userDisplayName.textContent = "Account";
  }

  async function getUserProfile(user) {
    const { data, error } = await supabaseClient
      .from("profiles")
      .select("display_name, avatar_url")
      .eq("id", user.id)
      .maybeSingle();

    if (error) {
      console.warn("Unable to load profile:", error.message);
      return null;
    }

    return data;
  }

  async function showLoggedInUI(session) {
    const user = session.user;
    const profile = await getUserProfile(user);

    const displayName =
      profile?.display_name ||
      user.user_metadata?.full_name ||
      user.user_metadata?.name ||
      user.email?.split("@")[0] ||
      "User";

    const avatarUrl =
      profile?.avatar_url ||
      user.user_metadata?.avatar_url ||
      user.user_metadata?.picture ||
      "";

    userDisplayName.textContent = displayName;

    if (avatarUrl) {
      userAvatar.src = avatarUrl;
      userAvatar.hidden = false;
    } else {
      userAvatar.hidden = true;
    }

    openLoginBtn.hidden = true;
    userPanel.hidden = false;
    closeLoginModal();
  }

  async function updateAuthUI(session) {
    if (session) {
      await showLoggedInUI(session);
    } else {
      showLoggedOutUI();
    }
  }

  openLoginBtn.addEventListener("click", openLoginModal);
  closeLoginBtn.addEventListener("click", closeLoginModal);

  loginModal.addEventListener("click", (event) => {
    if (event.target === loginModal) {
      closeLoginModal();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !loginModal.hidden) {
      closeLoginModal();
    }
  });

  googleLoginBtn.addEventListener("click", async () => {
    googleLoginBtn.disabled = true;
    authMessage.textContent = "Redirecting to Google...";

    const { error } = await supabaseClient.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: OAUTH_REDIRECT_URL
      }
    });

    if (error) {
      authMessage.textContent = "Login failed: " + error.message;
      googleLoginBtn.disabled = false;
    }
  });

  if (githubLoginBtn) githubLoginBtn.addEventListener("click", async () => {
  githubLoginBtn.disabled = true;
  authMessage.textContent = "Redirecting to GitHub...";

  const { error } = await supabaseClient.auth.signInWithOAuth({
    provider: "github",
    options: {
      redirectTo: OAUTH_REDIRECT_URL
    }
  });

  if (error) {
    authMessage.textContent = "GitHub login failed: " + error.message;
    githubLoginBtn.disabled = false;
  }
});

  logoutBtn.addEventListener("click", async () => {
    logoutBtn.disabled = true;

    const { error } = await supabaseClient.auth.signOut();

    if (error) {
      console.error("Logout failed:", error.message);
      logoutBtn.disabled = false;
      return;
    }

    showLoggedOutUI();
    logoutBtn.disabled = false;
  });

  /*
   * 监测登录、退出和 Session 更新。
   */
  supabaseClient.auth.onAuthStateChange((_event, session) => {
    window.setTimeout(() => {
      updateAuthUI(session);
    }, 0);
  });

  /*
   * 页面第一次打开时检查是否已经登录。
   */
  async function initialiseAuth() {
    const {
      data: { session },
      error
    } = await supabaseClient.auth.getSession();

    if (error) {
      console.error("Unable to read session:", error.message);
      showLoggedOutUI();
      return;
    }

    await updateAuthUI(session);
  }

  /*
   * 之后 Run Verification 可以使用这个方法检查用户。
   */
  window.truthScopeAuth = {
    async getSession() {
      const {
        data: { session }
      } = await supabaseClient.auth.getSession();

      return session;
    },

    async requireSession() {
      const session = await this.getSession();

      if (!session) {
        openLoginModal();
        return null;
      }

      return session;
    },

    openLogin: openLoginModal
  };

  initialiseAuth();
})();
