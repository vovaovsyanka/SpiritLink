using System;
using System.Collections;
using TMPro;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.Networking;
using UnityEngine.UI;

public class MessageSpawner : MonoBehaviour
{
    private class MessageResponse
    {
        public string text;
        public bool passed;
    }

    public class MessageRequest
    {
        public string level;
        public string text;
    }

    private const int RequestTimeoutSeconds = 150;

    public static event Action OnChatEnded;

    public bool IsRequestInProgress { get; private set; } = false;

    [SerializeField] private string serverUrl = "http://localhost:8000/predict";
    [Space(30)]
    [SerializeField] private TMP_InputField _inputField;
    [SerializeField] private Transform _contentTransform;
    [SerializeField] private ScrollRect _scrollRect;
    [SerializeField] private GameObject _myMessage;
    [SerializeField] private GameObject _AIMessage;
    [SerializeField] private GameObject _spaceMessage;
    [Space(30)]
    [SerializeField] private string _levelNameToServer;

    private InputSystem_Actions _inputSystem_Actions;

    private void OnEnable()
    {
        _inputSystem_Actions = new();
        _inputSystem_Actions.Enable();

        _inputSystem_Actions.Chat.ChatConfirm.performed += SpawnMessage;
    }

    private void OnDisable()
    {
        _inputSystem_Actions.Chat.ChatConfirm.performed -= SpawnMessage;

        _inputSystem_Actions.Disable();
    }

    public void SendMessageToServer(string text)
    {
        if (IsRequestInProgress)
        {
            Debug.LogWarning("Запрос уже выполняется!");
            return;
        }

        if (string.IsNullOrWhiteSpace(text))
        {
            Debug.LogWarning("Текст сообщения пуст!");
            return;
        }

        StartCoroutine(SendMessageCoroutine(text, _levelNameToServer));
    }

    private IEnumerator SendMessageCoroutine(string text, string level)
    {
        IEnumerator GenereteSpace()
        {
            yield return new WaitForEndOfFrame();
            LayoutRebuilder.ForceRebuildLayoutImmediate((RectTransform)_contentTransform);
            LayoutRebuilder.ForceRebuildLayoutImmediate((RectTransform)_scrollRect.transform);
            yield return new WaitForEndOfFrame();
            Instantiate(_spaceMessage, _contentTransform);
            yield return new WaitForEndOfFrame();
            LayoutRebuilder.ForceRebuildLayoutImmediate((RectTransform)_contentTransform);
            LayoutRebuilder.ForceRebuildLayoutImmediate((RectTransform)_scrollRect.transform);
            yield return new WaitForEndOfFrame();
        }

        if (Player.Instance != null)
            Player.Instance.CanAct = false;

        IsRequestInProgress = true;
        _inputField.interactable = false;

        // Формируем URL с параметром msg
        // UnityWebRequest.EscapeURL кодирует специальные символы для безопасной передачи
        string escapedMessage = UnityWebRequest.EscapeURL(text);
        string fullUrl = $"{serverUrl}";

        Debug.Log($"Отправка запроса: {fullUrl}");

        MessageRequest requestData = new()
        {
            level = level,
            text = text
        };

        string jsonData = JsonUtility.ToJson(requestData);
        byte[] bodyRaw = System.Text.Encoding.UTF8.GetBytes(jsonData);

        // Используем GET запрос вместо POST
        using (UnityWebRequest www = new("http://localhost:8000/predict", "POST"))
        {
            www.uploadHandler = new UploadHandlerRaw(bodyRaw)
            {
                contentType = "application/json" // Crucial: tells the server it's JSON
            };

            www.downloadHandler = new DownloadHandlerBuffer();
            // Без таймаута зависший сервер навсегда блокирует поле ввода (по умолчанию ожидание бесконечное).
            // Больше, чем таймаут LLM на сервере (120 с), чтобы сервер успел ответить текстом ошибки.
            www.timeout = RequestTimeoutSeconds;

            yield return www.SendWebRequest();

            if (www.result == UnityWebRequest.Result.Success)
            {
                yield return StartCoroutine(GenereteSpace());
                try
                {
                    MessageResponse response = JsonUtility.FromJson<MessageResponse>(www.downloadHandler.text);

                    TextMeshProUGUI currentMessage = Instantiate(_AIMessage, _contentTransform).transform.GetComponentInChildren<TextMeshProUGUI>();

                    if (response.passed)
                    {
                        currentMessage.text = "Уровень пройден. Поздравляю!";
                        OnChatEnded.Invoke();

                    }
                    else
                    {
                        currentMessage.text = response.text;

                    }

                    Debug.Log($"Получен ответ: {response.text}, прошел: {response.passed}");
                }
                catch (System.Exception e)
                {
                    Debug.LogError($"Ошибка парсинга ответа: {e.Message}");
                    Debug.Log($"Сырой ответ сервера: {www.downloadHandler.text}");
                }
                yield return StartCoroutine(GenereteSpace());
            }
            else
            {
                Debug.LogError($"Ошибка запроса: {www.error}");
                Debug.LogError($"HTTP код: {www.responseCode}");
            }
        }

        IsRequestInProgress = false;
        _inputField.interactable = true;
        _inputField.ActivateInputField(); // Возвращаем фокус на поле ввода

        if (Player.Instance != null)
            Player.Instance.CanAct = true;
    }

    private void SpawnMessage(InputAction.CallbackContext obj)
    {
        if (_inputField.text.Length > 0)
        {
            TextMeshProUGUI currentMessage = Instantiate(_myMessage, _contentTransform).transform.GetComponentInChildren<TextMeshProUGUI>();
            currentMessage.text = _inputField.text;

            LayoutRebuilder.ForceRebuildLayoutImmediate((RectTransform)_contentTransform);
            LayoutRebuilder.ForceRebuildLayoutImmediate((RectTransform)_scrollRect.transform);

            SendMessageToServer(_inputField.text);

            _inputField.text = "";

            _scrollRect.verticalNormalizedPosition = 0f;
        }
    }
}