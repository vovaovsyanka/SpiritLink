using System;
using System.Collections;
using System.Text;
using Core.Scripts.UI;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.SceneManagement;

namespace Core.Scripts.Network
{
    /// <summary>Результат запроса к серверу. StatusCode 0 — нет связи.</summary>
    public class ApiResult<T>
    {
        public bool Ok;
        public long StatusCode;
        public T Data;
        /// <summary>Текст ошибки для игрока.</summary>
        public string Error;
        /// <summary>Для 429: через сколько секунд можно повторить.</summary>
        public int RetryAfterSeconds;
    }

    [Serializable]
    public class EmptyResponse { }

    /// <summary>
    /// Связь с бэкендом. Создаётся сам до загрузки первой сцены и живёт всю игру.
    /// Токен сессии хранится в PlayerPrefs (в WebGL — в хранилище браузера), адрес сервера —
    /// в StreamingAssets/config.json. Если игрок не вошёл, показывает окно входа.
    /// </summary>
    public class ApiClient : MonoBehaviour
    {
        private const string TokenKey = "spiritlink_token";
        private const string DefaultServerUrl = "http://localhost:8000";
        private const string ConfigFileName = "config.json";
        // Больше таймаута LLM на сервере (120 с), чтобы сервер успел ответить текстом ошибки
        private const int TimeoutSeconds = 150;

        public static ApiClient Instance { get; private set; }
        public static event Action OnLoggedIn;
        public static event Action OnLoggedOut;

        public string ServerUrl { get; private set; } = DefaultServerUrl;
        /// <summary>Конфиг прочитан, сохранённый токен проверен.</summary>
        public bool IsReady { get; private set; }
        public bool IsLoggedIn => Progress != null && !string.IsNullOrEmpty(_token);
        public ProgressResponse Progress { get; private set; }

        private string _token;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        private static void Bootstrap()
        {
            var go = new GameObject("ApiClient");
            DontDestroyOnLoad(go);
            Instance = go.AddComponent<ApiClient>();
        }

        private void Awake()
        {
            _token = PlayerPrefs.GetString(TokenKey, "");
            SceneManager.sceneLoaded += OnSceneLoaded;
        }

        private void OnDestroy()
        {
            SceneManager.sceneLoaded -= OnSceneLoaded;
        }

        private IEnumerator Start()
        {
            yield return LoadConfig();

            string loginMessage = null;
            if (!string.IsNullOrEmpty(_token))
            {
                ApiResult<ProgressResponse> result = null;
                yield return LoadProgress(r => result = r);
                if (result.Ok)
                {
                    OnLoggedIn?.Invoke();
                }
                else if (result.StatusCode != 401)
                {
                    loginMessage = result.Error;
                }
            }

            IsReady = true;
            if (!IsLoggedIn)
            {
                LoginScreen.Show(loginMessage);
            }
        }

        private void OnSceneLoaded(Scene scene, LoadSceneMode mode)
        {
            LevelProgressController.AttachIfLevel(scene);

            // окно входа живёт в сцене, после смены сцены показываем заново
            if (IsReady && !IsLoggedIn)
            {
                LoginScreen.Show();
            }
        }

        private IEnumerator LoadConfig()
        {
            string path = Application.streamingAssetsPath + "/" + ConfigFileName;
            string url = path.Contains("://") ? path : new Uri(path).AbsoluteUri;

            using (var request = UnityWebRequest.Get(url))
            {
                yield return request.SendWebRequest();
                if (request.result != UnityWebRequest.Result.Success)
                {
                    Debug.LogWarning($"ApiClient: нет {ConfigFileName} ({request.error}), сервер {ServerUrl}");
                    yield break;
                }

                try
                {
                    var config = JsonUtility.FromJson<ServerConfigFile>(request.downloadHandler.text);
                    if (!string.IsNullOrWhiteSpace(config?.server_url))
                    {
                        ServerUrl = config.server_url.Trim().TrimEnd('/');
                    }
                }
                catch (Exception e)
                {
                    Debug.LogError($"ApiClient: не удалось прочитать {ConfigFileName}: {e.Message}");
                }
            }
            Debug.Log($"ApiClient: сервер {ServerUrl}");
        }

        // ── Аккаунт ──────────────────────────────────────────────────────────

        /// <summary>Вход (register = false) или регистрация. onDone(null) — успех, иначе текст ошибки.</summary>
        public Coroutine Authenticate(bool register, string login, string password, Action<string> onDone)
        {
            return StartCoroutine(AuthenticateRoutine(register, login, password, onDone));
        }

        private IEnumerator AuthenticateRoutine(bool register, string login, string password, Action<string> onDone)
        {
            ApiResult<TokenResponse> auth = null;
            yield return Send<TokenResponse>(
                "POST", register ? "/auth/register" : "/auth/login",
                new CredentialsRequest { login = login, password = password }, r => auth = r);

            if (!auth.Ok)
            {
                onDone?.Invoke(auth.Error);
                yield break;
            }

            SaveToken(auth.Data.token);
            ApiResult<ProgressResponse> progress = null;
            yield return LoadProgress(r => progress = r);
            if (!progress.Ok)
            {
                onDone?.Invoke(progress.Error);
                yield break;
            }

            onDone?.Invoke(null);
            OnLoggedIn?.Invoke();
        }

        public void Logout()
        {
            if (!string.IsNullOrEmpty(_token))
            {
                StartCoroutine(Send<EmptyResponse>("POST", "/auth/logout", null, null));
            }
            ClearSession();
        }

        private void SaveToken(string token)
        {
            _token = token ?? "";
            PlayerPrefs.SetString(TokenKey, _token);
            PlayerPrefs.Save();
        }

        private void ClearSession()
        {
            bool wasLoggedIn = IsLoggedIn;
            SaveToken("");
            Progress = null;
            if (wasLoggedIn)
            {
                OnLoggedOut?.Invoke();
            }
            LoginScreen.Show();
        }

        // ── Прогресс ─────────────────────────────────────────────────────────

        public Coroutine LoadProgress(Action<ApiResult<ProgressResponse>> onDone)
        {
            return StartCoroutine(Send<ProgressResponse>("GET", "/me/progress", null, r =>
            {
                if (r.Ok)
                {
                    Progress = r.Data;
                }
                onDone?.Invoke(r);
            }));
        }

        public PassState GetPass(string passId)
        {
            if (Progress?.passes == null) return null;
            foreach (var pass in Progress.passes)
            {
                if (pass.pass_id == passId) return pass;
            }
            return null;
        }

        /// <summary>Вход на уровень: создаёт, продолжает или начинает перепрохождение.</summary>
        public Coroutine StartPass(string passId, Action<ApiResult<PassState>> onDone)
        {
            return StartCoroutine(Send<PassState>("POST", $"/passes/{passId}/start", null, r =>
            {
                if (r.Ok)
                {
                    UpdatePass(r.Data);
                    if (Progress != null) Progress.current_pass_id = passId;
                }
                onDone?.Invoke(r);
            }));
        }

        public Coroutine AddClue(string passId, string clue, Action<ApiResult<PassState>> onDone)
        {
            return StartCoroutine(Send<PassState>(
                "POST", $"/passes/{passId}/clues", new ClueRequest { clue = clue }, r => AfterPassUpdate(r, onDone)));
        }

        /// <summary>Прочитанный разговор для журнала. Такой же разговор сервер повторно не запишет.</summary>
        public Coroutine AddJournalDialogue(string passId, JournalEntry[] entries, Action<ApiResult<PassState>> onDone)
        {
            return StartCoroutine(Send<PassState>(
                "POST", $"/passes/{passId}/journal", new JournalRequest { entries = entries }, r => AfterPassUpdate(r, onDone)));
        }

        public Coroutine SetPhase(string passId, string phase, Action<ApiResult<PassState>> onDone)
        {
            return StartCoroutine(Send<PassState>(
                "POST", $"/passes/{passId}/phase", new PhaseRequest { phase = phase }, r => AfterPassUpdate(r, onDone)));
        }

        private void AfterPassUpdate(ApiResult<PassState> result, Action<ApiResult<PassState>> onDone)
        {
            if (result.Ok)
            {
                UpdatePass(result.Data);
            }
            onDone?.Invoke(result);
        }

        private void UpdatePass(PassState state)
        {
            if (Progress?.passes == null || state == null) return;
            for (int i = 0; i < Progress.passes.Length; i++)
            {
                if (Progress.passes[i].pass_id == state.pass_id)
                {
                    Progress.passes[i] = state;
                    return;
                }
            }
        }

        // ── Уровень мира ─────────────────────────────────────────────────────

        public Coroutine GetWorldLevels(Action<ApiResult<WorldLevelsResponse>> onDone)
        {
            return StartCoroutine(Send<WorldLevelsResponse>("GET", "/world-levels", null, onDone));
        }

        public Coroutine SetWorldLevel(int level, Action<ApiResult<WorldLevelsResponse>> onDone)
        {
            return StartCoroutine(Send<WorldLevelsResponse>(
                "PUT", "/me/world-level", new WorldLevelRequest { world_level = level }, r =>
                {
                    if (r.Ok && Progress != null)
                    {
                        Progress.world_level = r.Data.current;
                    }
                    onDone?.Invoke(r);
                }));
        }

        // ── Свободный промпт ─────────────────────────────────────────────────

        public Coroutine Predict(string passId, string text, Action<ApiResult<PredictResponse>> onDone)
        {
            return StartCoroutine(Send<PredictResponse>(
                "POST", "/predict", new PredictRequest { pass_id = passId, text = text }, r =>
                {
                    if (r.Ok && r.Data.passed)
                    {
                        var pass = GetPass(passId);
                        if (pass != null)
                        {
                            pass.phase = Phases.Done;
                            pass.completed = true;
                        }
                    }
                    onDone?.Invoke(r);
                }));
        }

        // ── HTTP ─────────────────────────────────────────────────────────────

        private IEnumerator Send<T>(string method, string path, object body, Action<ApiResult<T>> onDone)
        {
            using (var request = new UnityWebRequest(ServerUrl + path, method))
            {
                if (body != null)
                {
                    request.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(JsonUtility.ToJson(body)));
                    request.SetRequestHeader("Content-Type", "application/json");
                }
                request.downloadHandler = new DownloadHandlerBuffer();
                request.timeout = TimeoutSeconds;
                if (!string.IsNullOrEmpty(_token))
                {
                    request.SetRequestHeader("Authorization", "Bearer " + _token);
                }

                yield return request.SendWebRequest();

                var result = new ApiResult<T> { StatusCode = request.responseCode };
                string text = request.downloadHandler != null ? request.downloadHandler.text : "";

                if (request.result == UnityWebRequest.Result.Success)
                {
                    result.Ok = true;
                    if (!string.IsNullOrEmpty(text) && typeof(T) != typeof(EmptyResponse))
                    {
                        try
                        {
                            result.Data = JsonUtility.FromJson<T>(text);
                        }
                        catch (Exception e)
                        {
                            Debug.LogError($"ApiClient: не удалось разобрать ответ {path}: {e.Message}\n{text}");
                            result.Ok = false;
                            result.Error = "Не удалось разобрать ответ сервера";
                        }
                    }
                }
                else
                {
                    result.Error = DescribeError(request, text);
                    int.TryParse(request.GetResponseHeader("Retry-After"), out result.RetryAfterSeconds);
                    Debug.LogWarning($"ApiClient: {method} {path} -> {request.responseCode}: {result.Error}");
                }

                // Сессия истекла или отозвана — просим войти заново (кроме самих запросов входа)
                if (result.StatusCode == 401 && !path.StartsWith("/auth/"))
                {
                    ClearSession();
                }

                onDone?.Invoke(result);
            }
        }

        private static string DescribeError(UnityWebRequest request, string text)
        {
            if (request.responseCode == 0)
            {
                return "Нет связи с сервером";
            }

            string detail = null;
            if (!string.IsNullOrEmpty(text))
            {
                try
                {
                    detail = JsonUtility.FromJson<ErrorResponse>(text)?.detail;
                }
                catch (Exception)
                {
                    // detail у ошибок валидации (422) — массив, его не разбираем
                }
            }
            if (!string.IsNullOrWhiteSpace(detail))
            {
                return detail;
            }

            switch (request.responseCode)
            {
                case 401: return "Нужно войти заново";
                case 422: return "Проверьте введённые данные";
                case 429: return "Слишком много запросов, подождите";
                default: return request.responseCode >= 500 ? "Ошибка сервера, попробуйте позже" : $"Ошибка {request.responseCode}";
            }
        }
    }
}
