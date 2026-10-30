using System;
using System.Collections;
using Core.Scripts.Network;
using TMPro;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.UI;

public class MessageSpawner : MonoBehaviour
{
    public static event Action OnChatEnded;

    public bool IsRequestInProgress { get; private set; } = false;

    [SerializeField] private TMP_InputField _inputField;
    [SerializeField] private Transform _contentTransform;
    [SerializeField] private ScrollRect _scrollRect;
    [SerializeField] private GameObject _myMessage;
    [SerializeField] private GameObject _AIMessage;
    [SerializeField] private GameObject _spaceMessage;
    [Space(30)]
    [Tooltip("pass_id уровня на сервере: tony_stark, subnautica, cyberpunk")]
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
            _scrollRect.verticalNormalizedPosition = 0f;
            yield return new WaitForEndOfFrame();
        }

        if (Player.Instance != null)
            Player.Instance.CanAct = false;

        IsRequestInProgress = true;
        _inputField.interactable = false;

        // Запрос идёт через ApiClient: адрес сервера из config.json, токен игрока, разбор ошибок
        ApiResult<PredictResponse> result = null;
        if (ApiClient.Instance != null)
        {
            yield return ApiClient.Instance.Predict(level, text, r => result = r);
        }

        yield return StartCoroutine(GenereteSpace());

        string reply;
        if (result != null && result.Ok)
        {
            if (result.Data.passed)
            {
                reply = "Уровень пройден. Поздравляю!";
                OnChatEnded?.Invoke();
            }
            else
            {
                reply = result.Data.text;
            }
            Debug.Log($"Получен ответ: {result.Data.text}, прошел: {result.Data.passed}");
        }
        else
        {
            reply = DescribeError(result);
        }
        AddMessage(_AIMessage, reply);
        yield return StartCoroutine(GenereteSpace());

        IsRequestInProgress = false;
        _inputField.interactable = true;
        _inputField.ActivateInputField(); // Возвращаем фокус на поле ввода

        if (Player.Instance != null)
            Player.Instance.CanAct = true;
    }

    private static string DescribeError(ApiResult<PredictResponse> result)
    {
        if (result == null) return "Нет связи с сервером.";
        switch (result.StatusCode)
        {
            case 429:
                return result.RetryAfterSeconds > 0
                    ? $"{result.Error}. Попробуйте через {result.RetryAfterSeconds} с."
                    : result.Error;
            case 409:
                return "Свободный промпт этого уровня ещё не открыт: сначала соберите паззл.";
            case 401:
                return "Нужно войти заново.";
            default:
                return result.Error;
        }
    }

    private void SpawnMessage(InputAction.CallbackContext obj)
    {
        // пока идёт запрос, новое сообщение не отправится — и в чате его показывать не нужно
        if (IsRequestInProgress || string.IsNullOrWhiteSpace(_inputField.text)) return;

        string text = _inputField.text;
        AddMessage(_myMessage, text);
        SendMessageToServer(text);
        _inputField.text = "";
    }

    /// <summary>Добавляет сообщение в чат, пересчитывает его размер и прокручивает чат к нему.</summary>
    private void AddMessage(GameObject prefab, string text)
    {
        var message = Instantiate(prefab, _contentTransform);
        message.GetComponentInChildren<TextMeshProUGUI>().text = text;

        // Блок сообщения — несколько вложенных ContentSizeFitter. За один общий пересчёт вложенные блоки
        // читают ещё старые размеры детей и выходят короче текста, поэтому считаем снизу вверх.
        RebuildBottomUp((RectTransform)message.transform);
        LayoutRebuilder.ForceRebuildLayoutImmediate((RectTransform)_contentTransform);
        LayoutRebuilder.ForceRebuildLayoutImmediate((RectTransform)_scrollRect.transform);
        _scrollRect.verticalNormalizedPosition = 0f;

        StartCoroutine(ScrollToBottomNextFrame());
    }

    private static void RebuildBottomUp(RectTransform rect)
    {
        foreach (Transform child in rect)
        {
            if (child is RectTransform childRect)
            {
                RebuildBottomUp(childRect);
            }
        }
        LayoutRebuilder.ForceRebuildLayoutImmediate(rect);
    }

    /// <summary>Подстраховка: после обработки разметки Unity в конце кадра высота контента ещё может измениться.</summary>
    private IEnumerator ScrollToBottomNextFrame()
    {
        yield return null;
        Canvas.ForceUpdateCanvases();
        _scrollRect.verticalNormalizedPosition = 0f;
    }
}
