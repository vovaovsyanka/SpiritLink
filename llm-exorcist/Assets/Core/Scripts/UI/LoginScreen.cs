using System.Text.RegularExpressions;
using Core.Scripts.Network;
using TMPro;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.UI;

namespace Core.Scripts.UI
{
    /// <summary>
    /// Окно входа и регистрации поверх любой сцены. Собирается из кода, сцену править не нужно.
    /// Показывает ApiClient, когда игрок не вошёл или сессия истекла.
    /// </summary>
    public class LoginScreen : MonoBehaviour
    {
        // Те же правила, что на сервере (bek-project/app/schemas.py)
        private static readonly Regex LoginPattern = new("^[A-Za-z0-9_.-]{3,32}$");
        private const int MinPasswordLength = 8;
        private const int MaxPasswordLength = 128;

        private static LoginScreen _current;

        private TMP_InputField _loginInput;
        private TMP_InputField _passwordInput;
        private TextMeshProUGUI _status;
        private Button _loginButton;
        private Button _registerButton;
        private bool _isBusy;
        private bool _blockedPlayer;

        public static bool IsShown => _current != null;

        public static void Show(string message = null)
        {
            if (_current == null)
            {
                RuntimeUi.EnsureEventSystem();
                var canvas = RuntimeUi.CreateCanvas("LoginScreen", 500);
                _current = canvas.gameObject.AddComponent<LoginScreen>();
                _current.Build(canvas.transform);
            }
            if (!string.IsNullOrEmpty(message))
            {
                _current.SetStatus(message, true);
            }
        }

        public static void Hide()
        {
            if (_current != null)
            {
                Destroy(_current.gameObject);
                _current = null;
            }
        }

        private void Build(Transform root)
        {
            // затемнение на весь экран — заодно перехватывает клики по игре
            var shade = RuntimeUi.CreatePanel(root, "Shade", new Color(0f, 0f, 0f, 0.85f),
                Vector2.zero, Vector2.one, Vector2.zero, Vector2.zero);

            var panel = RuntimeUi.CreatePanel(shade, "Panel", RuntimeUi.PanelColor,
                new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(-340, -300), new Vector2(340, 300));
            RuntimeUi.AddVerticalLayout(panel.gameObject, 40, 18);

            RuntimeUi.CreateText(panel, "LLM Exorcist", 52, 70).color = RuntimeUi.ButtonColor;
            RuntimeUi.CreateText(panel, "Войдите или зарегистрируйтесь, чтобы прогресс сохранялся", 26, 70);

            _loginInput = RuntimeUi.CreateInput(panel, "Логин (латиница, цифры, _ . -)", false, 32);
            _passwordInput = RuntimeUi.CreateInput(panel, "Пароль (от 8 символов)", true, MaxPasswordLength);

            var row = new GameObject("Buttons", typeof(RectTransform));
            row.transform.SetParent(panel, false);
            var rowLayout = row.AddComponent<HorizontalLayoutGroup>();
            rowLayout.spacing = 18;
            rowLayout.childControlWidth = true;
            rowLayout.childControlHeight = true;
            rowLayout.childForceExpandWidth = true;
            RuntimeUi.SetHeight(row, 64);

            _loginButton = RuntimeUi.CreateButton(row.transform, "Войти", () => Submit(false));
            _registerButton = RuntimeUi.CreateButton(row.transform, "Регистрация", () => Submit(true));

            _status = RuntimeUi.CreateText(panel, "", 26, 80);

            _loginInput.Select();
        }

        private void OnEnable()
        {
            if (Player.Instance != null && Player.Instance.CanAct)
            {
                Player.Instance.CanAct = false;
                _blockedPlayer = true;
            }
        }

        private void OnDestroy()
        {
            if (_current == this) _current = null;
            if (_blockedPlayer && Player.Instance != null)
            {
                Player.Instance.CanAct = true;
            }
        }

        private void Update()
        {
            var keyboard = Keyboard.current;
            if (keyboard == null || _isBusy) return;

            if (keyboard.enterKey.wasPressedThisFrame || keyboard.numpadEnterKey.wasPressedThisFrame)
            {
                Submit(false);
            }
            else if (keyboard.tabKey.wasPressedThisFrame)
            {
                (_loginInput.isFocused ? _passwordInput : _loginInput).Select();
            }
        }

        private void Submit(bool register)
        {
            if (_isBusy || ApiClient.Instance == null) return;

            string login = _loginInput.text.Trim();
            string password = _passwordInput.text;

            if (!LoginPattern.IsMatch(login))
            {
                SetStatus("Логин: 3–32 символа, латинские буквы, цифры, _ . -", true);
                return;
            }
            if (password.Length < MinPasswordLength)
            {
                SetStatus($"Пароль должен быть не короче {MinPasswordLength} символов", true);
                return;
            }

            SetBusy(true);
            SetStatus(register ? "Регистрация..." : "Вход...", false);
            ApiClient.Instance.Authenticate(register, login, password, error =>
            {
                if (this == null) return;  // окно уже закрыто (сменилась сцена)
                SetBusy(false);
                if (error == null)
                {
                    Hide();
                }
                else
                {
                    SetStatus(error, true);
                }
            });
        }

        private void SetBusy(bool busy)
        {
            _isBusy = busy;
            _loginButton.interactable = !busy;
            _registerButton.interactable = !busy;
        }

        private void SetStatus(string message, bool isError)
        {
            _status.text = message;
            _status.color = isError ? RuntimeUi.ErrorColor : RuntimeUi.TextColor;
        }
    }
}
