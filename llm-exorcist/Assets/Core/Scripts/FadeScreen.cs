using System;
using System.Collections;
using UnityEngine;
using UnityEngine.UI;

public class FadeScreen : MonoBehaviour
{
    [SerializeField] private Image _fadeImage;
    [SerializeField] private Animator _drivingTextAnimator;
    public static event EventHandler<OnFadingStartedEventArgs> OnFadingStarted;
    public static event EventHandler OnWaitAfterFadingStarted;

    public class OnFadingStartedEventArgs : EventArgs
    {
        public float FadingDuration;
    }
    
    
    private Color _color;

    private void Awake()
    {
        _color = _fadeImage.color;
    }

    public IEnumerator Fade(float duration = 1.5f, float waitAfterFadingDuration = 0f)
    {
        OnFadingStarted?.Invoke(this, new OnFadingStartedEventArgs { FadingDuration = duration });
        
        for (float i = 0; i <= duration; i+=.1f)
        {
            _color.a = i/duration;
            _fadeImage.color = _color;
            yield return new WaitForSeconds(.1f);
        }

        if (_fadeImage.color.a < 1f)
        {
            _color.a = 1f;
            _fadeImage.color = _color;
        }

        if (waitAfterFadingDuration > 0f)
        {
            _drivingTextAnimator.SetBool("IsDriving", true);
            OnWaitAfterFadingStarted?.Invoke(this, EventArgs.Empty);
            yield return new WaitForSeconds(waitAfterFadingDuration);
        }
    }

    public IEnumerator Appear(float duration = 1.5f)
    {
        _color.a = 1f;
        _fadeImage.color = _color;
        for (float i = 0; i <= duration; i+=.1f)
        {
            _color.a = 1f - i/duration;
            _fadeImage.color = _color;
            yield return new WaitForSeconds(.1f);
        }
        
        if (_fadeImage.color.a > 0f)
        {
            _color.a = 0f;
            _fadeImage.color = _color;
        }
    }
}
