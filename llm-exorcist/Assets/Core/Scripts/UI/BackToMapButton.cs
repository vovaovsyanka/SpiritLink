using Assets.Core.Scripts.Chat;
using TMPro;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

namespace Core.Scripts.UI
{
    /// <summary>
    /// Кнопка «На карту» в левом верхнем углу уровня. Собирается из кода, сцену править не нужно;
    /// её создаёт LevelProgressController при загрузке LVL1–3. Прогресс на сервере сохраняется по ходу
    /// игры, поэтому выйти на карту можно в любой момент — кроме диалога, чата, журнала и паузы:
    /// там кнопка неактивна, иначе у следующей сцены остались бы залипшие флаги этих окон.
    /// </summary>
    public class BackToMapButton : MonoBehaviour
    {
        private Button _button;
        private bool _isLoading;

        public static BackToMapButton Create(Scene scene)
        {
            RuntimeUi.EnsureEventSystem();
            var canvas = RuntimeUi.CreateCanvas("BackToMapButton", 90);
            SceneManager.MoveGameObjectToScene(canvas.gameObject, scene);

            var component = canvas.gameObject.AddComponent<BackToMapButton>();
            component.Build(canvas.transform);
            return component;
        }

        private void Build(Transform root)
        {
            _button = RuntimeUi.CreateButton(root, "На карту", GoToMap, 56);

            var rect = (RectTransform)_button.transform;
            rect.anchorMin = rect.anchorMax = rect.pivot = new Vector2(0f, 1f);
            rect.anchoredPosition = new Vector2(20f, -20f);
            rect.sizeDelta = new Vector2(240f, 56f);
        }

        private void Update()
        {
            _button.interactable = !_isLoading
                && !GameManager.IsGamePaused
                && !DialogueViewer.IsGoing
                && !ChatInteractor.IsChatOpen
                && !Journal.IsJournalOpen;
        }

        private void GoToMap()
        {
            if (_isLoading) return;
            _isLoading = true;

            if (GameManager.Instance != null)
            {
                GameManager.Instance.LoadMapScene();  // с затемнением, как остальные переходы
            }
            else
            {
                SceneManager.LoadScene(SceneInfo.MAP_SCENE);
            }
        }
    }
}
