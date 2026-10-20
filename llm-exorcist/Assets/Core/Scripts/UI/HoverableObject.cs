using TMPro;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace Core.Scripts.UI
{
    /// <summary>Показывает подсказку с переключением «текст / описание», если курсор задержался на объекте.</summary>
    public class HoverableObject : MonoBehaviour, IPointerEnterHandler, IPointerExitHandler
    {
        private const int HintSortingOrder = 100;
        private const float MaxHintGrowth = 1.5f;

        [Header("Objects")]
        [SerializeField] private GameObject _onHoverHint;
        [Header("UI elements")]
        [SerializeField] private Button _textButton;
        [SerializeField] private Button _infoButton;
        [Header("Settings")]
        [SerializeField] private string _textString;
        [SerializeField] private string _infoString;
        [SerializeField] private float _hintShowDelay = 0.5f;

        private TextMeshProUGUI _hintText;
        private RectTransform _hintRect;
        private float _baseHintHeight;

        private bool _isPointerOver;
        private bool _isTracking = true;
        private bool _isHintShown;
        private bool _showingInfo;
        private float _hoverTimer;

        private void Awake()
        {
            if (_onHoverHint == null) return;

            _hintText = _onHoverHint.GetComponentInChildren<TextMeshProUGUI>(true);
            _hintRect = _onHoverHint.GetComponent<RectTransform>();
            if (_hintRect != null) _baseHintHeight = _hintRect.rect.height;

            // подсказка рисуется поверх соседних блоков, при этом остаётся дочерней — иерархия блока не трогается
            if (!_onHoverHint.TryGetComponent(out Canvas hintCanvas))
            {
                hintCanvas = _onHoverHint.AddComponent<Canvas>();
            }
            hintCanvas.overrideSorting = true;
            hintCanvas.sortingOrder = HintSortingOrder;
            if (!_onHoverHint.TryGetComponent<GraphicRaycaster>(out _))
            {
                _onHoverHint.AddComponent<GraphicRaycaster>();
            }

            if (_textButton != null) _textButton.onClick.AddListener(ShowText);
            if (_infoButton != null) _infoButton.onClick.AddListener(ShowInfo);

            HideHint();
            ShowText();
        }

        private void OnDestroy()
        {
            if (_textButton != null) _textButton.onClick.RemoveListener(ShowText);
            if (_infoButton != null) _infoButton.onClick.RemoveListener(ShowInfo);
        }

        private void OnDisable()
        {
            _isPointerOver = false;
            _hoverTimer = 0f;
            HideHint();
        }

        private void Update()
        {
            if (!_isPointerOver || !_isTracking || _isHintShown) return;

            // unscaled — подсказка должна работать и на паузе (timeScale = 0)
            _hoverTimer += Time.unscaledDeltaTime;
            if (_hoverTimer >= _hintShowDelay)
            {
                ShowHint();
            }
        }

        public void SetHintText(string extendedText, string infoText)
        {
            _textString = extendedText;
            _infoString = infoText;
            RefreshHintText();
        }

        /// <summary>Отключает подсказку на время перетаскивания.</summary>
        public void SetHoverTracking(bool isTracking)
        {
            _isTracking = isTracking;
            _hoverTimer = 0f;

            if (!isTracking)
            {
                HideHint();
            }
        }

        public void OnPointerEnter(PointerEventData eventData)
        {
            _isPointerOver = true;
            _hoverTimer = 0f;
        }

        public void OnPointerExit(PointerEventData eventData)
        {
            _isPointerOver = false;
            _hoverTimer = 0f;
            HideHint();
        }

        private void ShowHint()
        {
            if (_onHoverHint == null) return;

            _isHintShown = true;
            _onHoverHint.SetActive(true);
            RefreshHintText();
        }

        private void HideHint()
        {
            _isHintShown = false;
            if (_onHoverHint != null)
            {
                _onHoverHint.SetActive(false);
            }
        }

        private void ShowText()
        {
            _showingInfo = false;
            RefreshHintText();
        }

        private void ShowInfo()
        {
            _showingInfo = true;
            RefreshHintText();
        }

        private void RefreshHintText()
        {
            if (_hintText == null) return;

            _hintText.text = _showingInfo ? _infoString : _textString;
            FitHintToText();
            HighlightActiveButton();
        }

        /// <summary>
        /// Возвращает подсказке исходный размер и растягивает её по высоте, только если текст не поместился
        /// даже после авто-размера шрифта. Высота ограничена, чтобы подсказка не заняла весь экран.
        /// </summary>
        private void FitHintToText()
        {
            if (_hintRect == null || _baseHintHeight <= 0f) return;

            _hintRect.SetSizeWithCurrentAnchors(RectTransform.Axis.Vertical, _baseHintHeight);
            if (!_isHintShown) return;

            _hintText.ForceMeshUpdate();
            if (!_hintText.isTextOverflowing) return;

            float overflow = _hintText.renderedHeight - _hintText.rectTransform.rect.height;
            float extra = Mathf.Clamp(overflow, 0f, _baseHintHeight * MaxHintGrowth);
            _hintRect.SetSizeWithCurrentAnchors(RectTransform.Axis.Vertical, _baseHintHeight + extra);
        }

        private void HighlightActiveButton()
        {
            SetButtonColor(_textButton, !_showingInfo);
            SetButtonColor(_infoButton, _showingInfo);
        }

        private static void SetButtonColor(Button button, bool isActive)
        {
            if (button == null || !button.TryGetComponent(out Image image)) return;

            image.color = isActive ? button.colors.pressedColor : button.colors.normalColor;
        }
    }
}
