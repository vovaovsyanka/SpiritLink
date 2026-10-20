using System;
using TMPro;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.SceneManagement;


public class MenuButton : MonoBehaviour
{
    [SerializeField] private TextMeshProUGUI _textChamber;
    [SerializeField] public UnityEvent OnPressMethod;

    public static event EventHandler OnPlayButtonPressed;
    public static event EventHandler OnHiddenButtonsNeedToSetActive;
    public static event EventHandler OnShowInfoPressed;
    public static event EventHandler OnHideInfoPressed;

    public TextMeshProUGUI TextChamber
    {
        get => _textChamber;
    }

    public void Play()
    {
        OnPlayButtonPressed?.Invoke(this, EventArgs.Empty);
    }

    public void ExitGame()
    {
        Application.Quit();
    }

    public void Resume()
    {
        GameManager.Instance.Resume();
    }

    public void BackToMenu()
    {
        OnHiddenButtonsNeedToSetActive?.Invoke(this, EventArgs.Empty);
    }

    public void AcceptBackToMenu()
    {
        GameManager.RestartGame();
    }

    public void RejectBackToMenu()
    {
        OnHiddenButtonsNeedToSetActive?.Invoke(this, EventArgs.Empty);
    }

    public void RestartSecretGameMode()
    {
        Time.timeScale = 1f;
        SceneManager.LoadScene(SceneInfo.SECRET_GAME_MODE_SCENE);
    }

    public void ShowInfo()
    {
        OnShowInfoPressed?.Invoke(this, EventArgs.Empty);
    }

    public void HideInfo()
    {
        OnHideInfoPressed?.Invoke(this, EventArgs.Empty);
    }
}
