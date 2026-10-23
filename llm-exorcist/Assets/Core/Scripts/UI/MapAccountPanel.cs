using System.Collections.Generic;
using Core.Scripts.Network;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace Core.Scripts.UI
{
    /// <summary>
    /// Панель в правом верхнем углу карты: игрок, сколько миров пройдено, выбор уровня мира
    /// (сложность классификатора) и выход. Собирается из кода — создаёт её MapManager.
    /// </summary>
    public class MapAccountPanel : MonoBehaviour
    {
        private TextMeshProUGUI _playerLabel;
        private Button _worldLevelButton;
        private RectTransform _levelsList;
        private readonly List<GameObject> _levelButtons = new();
        private bool _isBusy;

        public static MapAccountPanel Create()
        {
            RuntimeUi.EnsureEventSystem();
            var canvas = RuntimeUi.CreateCanvas("MapAccountPanel", 100);
            var panel = canvas.gameObject.AddComponent<MapAccountPanel>();
            panel.Build(canvas.transform);
            return panel;
        }

        private void Build(Transform root)
        {
            var box = RuntimeUi.CreatePanel(root, "Account", RuntimeUi.PanelColor,
                new Vector2(1f, 1f), new Vector2(1f, 1f), new Vector2(-460, -260), new Vector2(-20, -20));
            RuntimeUi.AddVerticalLayout(box.gameObject, 16, 10);

            _playerLabel = RuntimeUi.CreateText(box, "", 26, 64);
            _worldLevelButton = RuntimeUi.CreateButton(box, "Сложность мира", ToggleLevelsList, 56);
            RuntimeUi.CreateButton(box, "Выйти из аккаунта", () => ApiClient.Instance.Logout(), 56);

            _levelsList = RuntimeUi.CreatePanel(root, "WorldLevels", RuntimeUi.PanelColor,
                new Vector2(1f, 1f), new Vector2(1f, 1f), new Vector2(-460, -620), new Vector2(-20, -270));
            RuntimeUi.AddVerticalLayout(_levelsList.gameObject, 16, 10);
            _levelsList.gameObject.SetActive(false);

            Refresh();
            // вернулись на карту с уровня — подтягиваем свежий прогресс
            if (ApiClient.Instance != null && ApiClient.Instance.IsLoggedIn)
            {
                ApiClient.Instance.LoadProgress(_ =>
                {
                    if (this != null) Refresh();
                });
            }
        }

        private void OnEnable()
        {
            ApiClient.OnLoggedIn += Refresh;
            ApiClient.OnLoggedOut += Refresh;
        }

        private void OnDisable()
        {
            ApiClient.OnLoggedIn -= Refresh;
            ApiClient.OnLoggedOut -= Refresh;
        }

        private void Refresh()
        {
            if (_playerLabel == null) return;

            var api = ApiClient.Instance;
            bool loggedIn = api != null && api.IsLoggedIn;
            _playerLabel.transform.parent.gameObject.SetActive(loggedIn);
            if (!loggedIn)
            {
                _levelsList.gameObject.SetActive(false);
                return;
            }

            var progress = api.Progress;
            int completed = 0;
            foreach (var pass in progress.passes)
            {
                if (pass.completed) completed++;
            }
            _playerLabel.text = $"{progress.display_name}\nПройдено миров: {completed} из {progress.passes.Length}";
            RuntimeUi.SetButtonLabel(_worldLevelButton, $"Сложность мира: {progress.world_level}");
        }

        private void ToggleLevelsList()
        {
            if (_levelsList.gameObject.activeSelf)
            {
                _levelsList.gameObject.SetActive(false);
                return;
            }
            if (_isBusy) return;

            _isBusy = true;
            ApiClient.Instance.GetWorldLevels(result =>
            {
                if (this == null) return;
                _isBusy = false;
                if (!result.Ok)
                {
                    RuntimeUi.Toast(result.Error);
                    return;
                }
                ShowLevels(result.Data);
            });
        }

        private void ShowLevels(WorldLevelsResponse data)
        {
            foreach (var button in _levelButtons)
            {
                Destroy(button);
            }
            _levelButtons.Clear();

            foreach (var info in data.levels)
            {
                int level = info.level;
                // без символов вроде ✓: в пиксельном шрифте игры их может не быть
                string label = $"{info.level}. {info.name}" + (info.level == data.current ? " (выбран)" : "")
                    + (info.available ? "" : " (нет модели)");
                var button = RuntimeUi.CreateButton(_levelsList, label, () => SelectLevel(level), 56);
                button.interactable = info.available && info.level != data.current;
                _levelButtons.Add(button.gameObject);
            }
            _levelsList.gameObject.SetActive(true);
        }

        private void SelectLevel(int level)
        {
            if (_isBusy) return;

            _isBusy = true;
            ApiClient.Instance.SetWorldLevel(level, result =>
            {
                if (this == null) return;
                _isBusy = false;
                if (!result.Ok)
                {
                    RuntimeUi.Toast(result.Error);
                    return;
                }
                ShowLevels(result.Data);
                Refresh();
            });
        }
    }
}
