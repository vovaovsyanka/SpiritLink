using System;
using System.Collections;
using UnityEngine;
using UnityEngine.SceneManagement;

public class MusicManager : MonoBehaviour
{
    [SerializeField] private AudioSource _audioSource;
    [SerializeField] private AudioClipRefsSO _audioClipRefsSO;

    public static event EventHandler OnHappySoundtrackFinished;
    public static MusicManager Instance { get; private set; }
    private bool _hasMusicFinished;

    private void Awake()
    {
        if (Instance == null)
        {
            Instance = this;
        }
        else
        {
            Destroy(gameObject);
        }
    }
    
    private void Start()
    {
        FadeScreen.OnFadingStarted += FadeScreen_OnFadingStarted;
        GameStateManager.OnStateChanged += GameStateManager_OnStateChanged;
        DialogueSetter.OnGoodResultDialogue += DialogueSetter_OnGoodResultDialogue;
            
        if (GameStateManager.State == GameState.ExamsPassed 
            && SceneManager.GetActiveScene().name != SceneInfo.HAPPY_END_SCENE)
        {
            _audioSource.resource = _audioClipRefsSO.BirdSinging;
            _audioSource.Play();
        }
    }

    private void DialogueSetter_OnGoodResultDialogue(object sender, EventArgs e)
    {
        StartCoroutine(ExamPassedTransition(2f));
    }   

    private void GameStateManager_OnStateChanged(object sender, GameStateManager.OnStateChangedEventArgs e)
    {
        if (e.CurrentState == GameState.ExamsFailed)
        {
            _audioSource.Stop();
        }
    }

    private void Update()
    {
        if (SceneManager.GetActiveScene().name == SceneInfo.HAPPY_END_SCENE)
        {
            if (_audioSource.time >=_audioSource.clip.length && !_hasMusicFinished)
            {
                _hasMusicFinished = true;
                OnHappySoundtrackFinished?.Invoke(this, EventArgs.Empty);
            }
        }
    }

    private void FadeScreen_OnFadingStarted(object sender, FadeScreen.OnFadingStartedEventArgs e)
    {
        StartCoroutine(Subside(e.FadingDuration));
    }

    private IEnumerator Subside(float duration)
    {
        float defaultVolume = _audioSource.volume;
        
        for (float i = 0; i <= duration; i+=.1f)
        {
            _audioSource.volume -= (defaultVolume/(duration/.1f));
            yield return new WaitForSeconds(.1f);
        }

        if (_audioSource.volume > 0f)
        {
            _audioSource.volume = 0f;
        }
    }

    private IEnumerator ExamPassedTransition(float subsideDuration)
    {
        float defaultVolume = _audioSource.volume;
        yield return StartCoroutine(Subside(subsideDuration));
        _audioSource.clip = _audioClipRefsSO.GoodExamResult;
        _audioSource.volume = defaultVolume;
        _audioSource.Play();
        _audioSource.loop = false;
    }

    public void PauseSoundtrack()
    {
        _audioSource.Pause();
    }

    public void ResumeSoundtrack()
    {
        _audioSource.UnPause();
    }

    private void OnDisable()
    {
        FadeScreen.OnFadingStarted -= FadeScreen_OnFadingStarted;
        GameStateManager.OnStateChanged -= GameStateManager_OnStateChanged;
        DialogueSetter.OnGoodResultDialogue -= DialogueSetter_OnGoodResultDialogue;

    }
}
