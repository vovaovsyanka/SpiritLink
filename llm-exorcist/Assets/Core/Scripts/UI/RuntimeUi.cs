using System;
using TMPro;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem.UI;
using UnityEngine.UI;

namespace Core.Scripts.UI
{
    /// <summary>
    /// Построение простого интерфейса из кода (окно входа, панель аккаунта, всплывающие сообщения),
    /// чтобы не править сцены. Шрифт берётся у любого текста сцены, иначе — шрифт TMP по умолчанию.
    /// </summary>
    public static class RuntimeUi
    {
        public static readonly Color PanelColor = new(0.09f, 0.13f, 0.24f, 0.97f);
        public static readonly Color ButtonColor = new(0.91f, 0.27f, 0.38f, 1f);
        public static readonly Color InputColor = new(0.06f, 0.06f, 0.14f, 1f);
        public static readonly Color TextColor = new(0.93f, 0.93f, 0.93f, 1f);
        public static readonly Color ErrorColor = new(1f, 0.42f, 0.42f, 1f);

        public static TMP_FontAsset Font
        {
            get
            {
                var sceneText = UnityEngine.Object.FindAnyObjectByType<TMP_Text>(FindObjectsInactive.Include);
                return sceneText != null && sceneText.font != null ? sceneText.font : TMP_Settings.defaultFontAsset;
            }
        }

        public static void EnsureEventSystem()
        {
            if (UnityEngine.Object.FindAnyObjectByType<EventSystem>(FindObjectsInactive.Include) != null) return;
            new GameObject("EventSystem", typeof(EventSystem), typeof(InputSystemUIInputModule));
        }

        public static Canvas CreateCanvas(string name, int sortingOrder)
        {
            var go = new GameObject(name, typeof(Canvas), typeof(CanvasScaler), typeof(GraphicRaycaster));
            var canvas = go.GetComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvas.sortingOrder = sortingOrder;

            var scaler = go.GetComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1920, 1080);
            scaler.matchWidthOrHeight = 0.5f;
            return canvas;
        }

        /// <summary>Прямоугольник с фоном. Якоря и смещения — как в RectTransform.</summary>
        public static RectTransform CreatePanel(Transform parent, string name, Color color,
            Vector2 anchorMin, Vector2 anchorMax, Vector2 offsetMin, Vector2 offsetMax)
        {
            var go = new GameObject(name, typeof(RectTransform), typeof(Image));
            go.transform.SetParent(parent, false);
            go.GetComponent<Image>().color = color;

            var rect = (RectTransform)go.transform;
            rect.anchorMin = anchorMin;
            rect.anchorMax = anchorMax;
            rect.offsetMin = offsetMin;
            rect.offsetMax = offsetMax;
            return rect;
        }

        public static VerticalLayoutGroup AddVerticalLayout(GameObject go, int padding, float spacing)
        {
            var layout = go.AddComponent<VerticalLayoutGroup>();
            layout.padding = new RectOffset(padding, padding, padding, padding);
            layout.spacing = spacing;
            layout.childControlWidth = true;
            layout.childControlHeight = true;
            layout.childForceExpandWidth = true;
            layout.childForceExpandHeight = false;
            return layout;
        }

        public static TextMeshProUGUI CreateText(Transform parent, string text, float size, float height,
            TextAlignmentOptions alignment = TextAlignmentOptions.Center)
        {
            var go = new GameObject("Text", typeof(RectTransform), typeof(TextMeshProUGUI));
            go.transform.SetParent(parent, false);

            var label = go.GetComponent<TextMeshProUGUI>();
            label.font = Font;
            label.text = text;
            label.fontSize = size;
            label.color = TextColor;
            label.alignment = alignment;  // перенос строк у нового текста TMP включён по умолчанию
            label.raycastTarget = false;
            SetHeight(go, height);
            return label;
        }

        public static TMP_InputField CreateInput(Transform parent, string placeholder, bool password, int characterLimit)
        {
            var go = TMP_DefaultControls.CreateInputField(new TMP_DefaultControls.Resources());
            go.transform.SetParent(parent, false);
            go.GetComponent<Image>().color = InputColor;

            var input = go.GetComponent<TMP_InputField>();
            input.characterLimit = characterLimit;
            input.contentType = password ? TMP_InputField.ContentType.Password : TMP_InputField.ContentType.Standard;
            input.lineType = TMP_InputField.LineType.SingleLine;

            var font = Font;
            if (input.textComponent is TextMeshProUGUI text)
            {
                text.font = font;
                text.fontSize = 32;
                text.color = TextColor;
            }
            if (input.placeholder is TextMeshProUGUI hint)
            {
                hint.font = font;
                hint.fontSize = 32;
                hint.text = placeholder;
                hint.color = new Color(1f, 1f, 1f, 0.35f);
            }
            SetHeight(go, 64);
            return input;
        }

        public static Button CreateButton(Transform parent, string label, Action onClick, float height = 64)
        {
            var go = TMP_DefaultControls.CreateButton(new TMP_DefaultControls.Resources());
            go.transform.SetParent(parent, false);
            go.GetComponent<Image>().color = ButtonColor;

            var text = go.GetComponentInChildren<TextMeshProUGUI>();
            if (text != null)
            {
                text.font = Font;
                text.text = label;
                text.fontSize = 30;
                text.color = Color.white;
            }

            var button = go.GetComponent<Button>();
            if (onClick != null)
            {
                button.onClick.AddListener(() => onClick());
            }
            SetHeight(go, height);
            return button;
        }

        public static void SetButtonLabel(Button button, string label)
        {
            var text = button.GetComponentInChildren<TextMeshProUGUI>();
            if (text != null) text.text = label;
        }

        public static void SetHeight(GameObject go, float height)
        {
            // без ??: у отсутствующего компонента Unity в редакторе возвращает «фальшивый null»
            if (!go.TryGetComponent(out LayoutElement element))
            {
                element = go.AddComponent<LayoutElement>();
            }
            element.preferredHeight = height;
            element.minHeight = height;
        }

        /// <summary>Сообщение вверху экрана на несколько секунд (например, «нет связи с сервером»).</summary>
        public static void Toast(string message, float seconds = 4f)
        {
            var canvas = CreateCanvas("Toast", 600);
            var panel = CreatePanel(canvas.transform, "ToastPanel", PanelColor,
                new Vector2(0.2f, 1f), new Vector2(0.8f, 1f), new Vector2(0, -130), new Vector2(0, -30));
            panel.GetComponent<Image>().raycastTarget = false;

            var text = CreateText(panel, message, 30, 0);
            var rect = (RectTransform)text.transform;
            rect.anchorMin = Vector2.zero;
            rect.anchorMax = Vector2.one;
            rect.offsetMin = new Vector2(20, 10);
            rect.offsetMax = new Vector2(-20, -10);

            UnityEngine.Object.Destroy(canvas.gameObject, seconds);
        }
    }
}
