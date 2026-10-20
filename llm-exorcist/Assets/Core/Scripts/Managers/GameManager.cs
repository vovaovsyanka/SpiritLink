using System;
using System.Collections;
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.SceneManagement;


public class GameManager : MonoBehaviour
{
    public static GameManager Instance { get; private set; }
    public static bool IsGamePaused { get; private set; }
    
    [SerializeField] private FadeScreen _fadeScreen;
    [SerializeField] private GameObject _pauseMenu;
    
    private Coroutine _fadeScreenCoroutine;
    private bool _canBePaused = true;
    private bool _isSceneLoading;

    private void Awake()
    {
        if (Instance == null)
        {
            Instance = this;
        }
    }

    private void Start()
    {
        Door.OnDoorOpen += Door_OnDoorOpen;
        MapManager.OnMapButtonClick += MapManager_OnMapButtonClick;
        InputManager.Instance.OnPauseAction += InputManager_OnPauseAction;
        
        if (GameStateManager.State == GameState.FirstEntry 
            && SceneManager.GetActiveScene().name != SceneInfo.MAIN_MENU_SCENE)
        {
            GameStateManager.State = SceneInfo.SceneStates[SceneManager.GetActiveScene().name];
        }

        _pauseMenu.SetActive(false);
        _fadeScreenCoroutine = StartCoroutine(_fadeScreen.Appear(1.5f));
    }

    private void InputManager_OnPauseAction(object sender, EventArgs e)
    {
        if (SceneManager.GetActiveScene().name != SceneInfo.MAIN_MENU_SCENE)
        {
            Pause();
        }
    }

    private void Door_OnDoorOpen(object sender, Door.OnDoorOpenEventArgs e)
    {
        if (Player.Instance != null)
        {
            Player.Instance.CanAct = false;
        }

        StartCoroutine(LoadScene(e.SceneToLoadName));
    }

    public void LoadMapScene()
    {
        if (Player.Instance != null)
        {
            Player.Instance.CanAct = false;
        }

        StartCoroutine(LoadScene("Map"));
    }

    

    private void MapManager_OnMapButtonClick(object sender, MapManager.OnMapButtonClickEventArgs e)
    {
        StartCoroutine(LoadScene(e.SceneToLoadName));
    }

    private IEnumerator LoadScene(string sceneName, float duration = 1.5f)
    {
        if (_isSceneLoading)
        {
            yield break;
        }
        _isSceneLoading = true;
        _canBePaused = false;
        float waitAfterFadingDuration = 0f;     

        GameStateManager.PreviousSceneName = SceneManager.GetActiveScene().name;

        if (_fadeScreenCoroutine != null)
        {
            StopCoroutine(_fadeScreenCoroutine);
        }
        yield return StartCoroutine(_fadeScreen.Fade(duration, waitAfterFadingDuration));

        SceneManager.LoadScene(sceneName);
    }

    private void Pause()
    {
        if (_canBePaused && !DialogueViewer.IsGoing)
        {
            if (!IsGamePaused)
            {
                Time.timeScale = 0f;
                _pauseMenu.SetActive(true);
                IsGamePaused = true;

                if (Player.Instance != null)
                {
                    Player.Instance.CanAct = false;
                }
            }
            else
            {
                Resume();
            }
        }
    }

    public void Resume()
    {
        _pauseMenu.SetActive(false);
        Time.timeScale = 1f;
        if (Player.Instance != null)
        {
            Player.Instance.CanAct = true;
        }

        IsGamePaused = false;
    }

    private void OnDisable()
    {
        Door.OnDoorOpen -= Door_OnDoorOpen;
        MapManager.OnMapButtonClick -= MapManager_OnMapButtonClick;
        InputManager.Instance.OnPauseAction -= InputManager_OnPauseAction;
    }

    public static void TimeScaleZeroInvoke(object sender, EventArgs e, EventHandler eventToInvoke)
    {
        Time.timeScale = 1f;
        eventToInvoke?.Invoke(sender, e);
        if (IsGamePaused)
        {
            Time.timeScale = 0f;
        }
    }

    public static void TimeScaleZeroInvoke(UnityEvent unityEvent)
    {
        Time.timeScale = 1f;
        unityEvent?.Invoke();
        if (IsGamePaused)
        {
            Time.timeScale = 0f;
        }
    }

    public static void RestartGame()
    {
        IsGamePaused = false;
        Time.timeScale = 1f;

        SceneManager.LoadScene(SceneInfo.MAP_SCENE);
    }
}
